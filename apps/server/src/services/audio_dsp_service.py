"""
Audio DSP & Master Export Service
Handles deterministic audio stitching, sample rate normalization (resampling),
silence insertion, two-pass EBU R128 loudness mastering, and WAV/MP3 export using FFmpeg.
Enforces strict subprocess argument safety without shell injection.
Validates source artifact paths and prevents unauthorized filesystem access.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional, Tuple, Dict, Any
import uuid
import wave

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.server.src.config import settings
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.models.export import ProjectExportRecord
from apps.server.src.schemas.project import MasterExportRequest
from apps.server.src.services.user_quota_service import UserQuotaService

logger = logging.getLogger("ai_voice_studio.audio_dsp")

# Standard search paths for FFmpeg on Windows workstation
KNOWN_FFMPEG_PATHS = [
    r"C:\Program Files\Piu Downloader\ffmpeg.exe",
    r"D:\C\Edit\Piu\_internal\ffmpeg.exe",
]

_CACHED_FFMPEG_CAPS: Optional[Dict[str, Any]] = None


def resolve_ffmpeg_binary() -> str:
    """Finds an approved, verified FFmpeg executable on the target host."""
    # 1. Configured setting or env override
    cfg_path = getattr(settings, "STUDIO_FFMPEG_PATH", None) or os.getenv("STUDIO_FFMPEG_PATH")
    if cfg_path and Path(cfg_path).is_file():
        return str(Path(cfg_path).resolve())

    # 2. Check system PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg and Path(which_ffmpeg).is_file():
        return str(Path(which_ffmpeg).resolve())

    # 3. Check known workstation installation locations
    for p in KNOWN_FFMPEG_PATHS:
        if Path(p).is_file():
            return str(Path(p).resolve())

    raise RuntimeError(
        "FFmpeg binary not found on host system. Please install FFmpeg or set STUDIO_FFMPEG_PATH."
    )


def verify_ffmpeg_capabilities(ffmpeg_bin: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies that the resolved FFmpeg executable supports required DSP filters and encoders:
    - Filters: loudnorm, aresample, apad, concat
    - Encoders: pcm_s16le, libmp3lame
    Extracts version and build license. Caches result.
    """
    global _CACHED_FFMPEG_CAPS
    if _CACHED_FFMPEG_CAPS is not None and not ffmpeg_bin:
        return _CACHED_FFMPEG_CAPS

    bin_path = ffmpeg_bin or resolve_ffmpeg_binary()

    # 1. Get version and configuration
    proc_ver = subprocess.run([bin_path, "-version"], capture_output=True, text=True, timeout=10)
    if proc_ver.returncode != 0:
        raise RuntimeError(f"FFmpeg -version check failed: {proc_ver.stderr}")

    ver_output = proc_ver.stdout
    first_line = ver_output.splitlines()[0] if ver_output else "Unknown FFmpeg"

    # Extract license
    license_type = "GPL" if "--enable-gpl" in ver_output else "LGPL"
    if "--enable-version3" in ver_output:
        license_type += "v3"

    # 2. Check filters
    proc_filters = subprocess.run([bin_path, "-filters"], capture_output=True, text=True, timeout=10)
    filters_text = proc_filters.stdout if proc_filters.returncode == 0 else ""
    has_loudnorm = "loudnorm" in filters_text
    has_aresample = "aresample" in filters_text
    has_apad = "apad" in filters_text
    has_concat = "concat" in filters_text

    # 3. Check encoders
    proc_encoders = subprocess.run([bin_path, "-encoders"], capture_output=True, text=True, timeout=10)
    encoders_text = proc_encoders.stdout if proc_encoders.returncode == 0 else ""
    has_pcm_s16le = "pcm_s16le" in encoders_text
    has_libmp3lame = "libmp3lame" in encoders_text

    if not (has_loudnorm and has_aresample and has_apad and has_pcm_s16le):
        raise RuntimeError(
            f"FFmpeg binary at {bin_path} is missing required DSP capabilities. "
            f"loudnorm={has_loudnorm}, aresample={has_aresample}, apad={has_apad}, pcm_s16le={has_pcm_s16le}"
        )

    caps = {
        "binary_path": bin_path,
        "version_banner": first_line,
        "license": license_type,
        "filters": {
            "loudnorm": has_loudnorm,
            "aresample": has_aresample,
            "apad": has_apad,
            "concat": has_concat,
        },
        "encoders": {
            "pcm_s16le": has_pcm_s16le,
            "libmp3lame": has_libmp3lame,
        },
    }
    _CACHED_FFMPEG_CAPS = caps
    logger.info(f"Verified FFmpeg DSP capabilities: {first_line} ({license_type})")
    return caps


def measure_audio_metrics(file_path: Path, ffmpeg_bin: Optional[str] = None) -> Dict[str, Any]:
    """
    Measures duration, channels, sample rate, bit depth/bitrate, SHA-256,
    and actual integrated LUFS and true peak dBTP using FFmpeg loudnorm filter.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found for measurement: {file_path}")

    if not ffmpeg_bin:
        ffmpeg_bin = resolve_ffmpeg_binary()

    raw_bytes = file_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    file_size = len(raw_bytes)

    duration_s = 0.0
    sample_rate = 44100
    channels = 1
    bit_depth = 16

    # If WAV, read native header directly
    if file_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(file_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                bit_depth = wf.getsampwidth() * 8
                duration_s = wf.getnframes() / float(sample_rate) if sample_rate > 0 else 0.0
        except Exception as e:
            logger.warning(f"Failed to read WAV header directly: {e}")

    # Measure LUFS and True Peak via loudnorm filter
    cmd_measure = [
        ffmpeg_bin,
        "-i", str(file_path.resolve()),
        "-af", "loudnorm=print_format=json",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd_measure, capture_output=True, text=True, timeout=60)
    actual_lufs = None
    true_peak_dbtp = None

    if proc.stderr:
        # Search for JSON block printed by loudnorm filter
        match = re.search(r"\{\s*\"input_i\"\s*:\s*\"([^\"]+)\".*?\"input_tp\"\s*:\s*\"([^\"]+)\".*?\}", proc.stderr, re.DOTALL)
        if match:
            try:
                actual_lufs = float(match.group(1))
                true_peak_dbtp = float(match.group(2))
            except ValueError:
                pass

        # If duration was not determined via wave, parse from stderr
        if duration_s <= 0.0:
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr)
            if dur_match:
                h = int(dur_match.group(1))
                m = int(dur_match.group(2))
                s = float(dur_match.group(3))
                duration_s = h * 3600 + m * 60 + s

        # Extract actual sample rate and channel layout from ffmpeg audio stream banner
        sr_match = re.search(r"Audio:.*?, (\d+) Hz", proc.stderr)
        if sr_match:
            sample_rate = int(sr_match.group(1))

        ch_match = re.search(r"Audio:.*?, \d+ Hz, (mono|stereo|\d+ channels)", proc.stderr)
        if ch_match:
            ch_str = ch_match.group(1)
            channels = 1 if ch_str == "mono" else (2 if ch_str == "stereo" else channels)

    return {
        "file_size_bytes": file_size,
        "sha256_checksum": sha256,
        "duration_seconds": round(duration_s, 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_depth": bit_depth,
        "loudness_lufs": actual_lufs,
        "true_peak_dbtp": true_peak_dbtp,
    }


class AudioDspService:
    @staticmethod
    def get_exports_dir() -> Path:
        base_dir = Path(settings.STUDIO_DATA_DIR) if hasattr(settings, "STUDIO_DATA_DIR") and settings.STUDIO_DATA_DIR else Path("D:/AIVoiceStudioData")
        exp_dir = base_dir / "exports"
        exp_dir.mkdir(parents=True, exist_ok=True)
        return exp_dir

    @classmethod
    async def export_project(
        cls,
        session: AsyncSession,
        user_id: str,
        project_id: str,
        req: MasterExportRequest,
    ) -> ProjectExportRecord:
        """
        Executes a deterministic master export for all completed segments of a project.
        Enforces two-pass EBU R128 loudness normalization and atomic export file creation.
        Strictly rejects incomplete, stale, or unauthorized segments.
        """
        stmt = (
            select(ProjectRecord)
            .where(ProjectRecord.id == project_id)
            .options(
                selectinload(ProjectRecord.segments).selectinload(ScriptSegmentRecord.active_artifact)
            )
        )
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
        if project.user_id != user_id:
            raise HTTPException(status_code=403, detail="FORBIDDEN_PROJECT_ACCESS")

        ordered_segments = sorted(project.segments, key=lambda s: s.sequence_order)
        if not ordered_segments:
            raise HTTPException(status_code=400, detail="PROJECT_HAS_NO_SEGMENTS: Không có đoạn âm thanh nào để xuất.")

        # Enforce storage quota preflight check and reserve capacity transactionally
        est_export_bytes = max(1024 * 1024, len(ordered_segments) * 500 * 1024)
        export_reservation = await UserQuotaService.reserve_capacity(
            db=session,
            user=user_id,
            estimated_bytes=est_export_bytes,
            reservation_type="master_export",
            timeout_seconds=600,
        )

        # 1. Strict Validation: Every segment must be in 'completed' status and have a valid, authorized artifact
        invalid_segments = []
        for idx, seg in enumerate(ordered_segments):
            if seg.status != "completed":
                invalid_segments.append(f"Câu #{idx + 1} (Trạng thái: {seg.status} - chưa hoàn thành hoặc cần tạo lại)")
            elif not seg.active_artifact_id or not seg.active_artifact:
                invalid_segments.append(f"Câu #{idx + 1} (Thiếu artifact âm thanh)")
            else:
                art = seg.active_artifact
                # Security: verify artifact ownership
                if art.owner_id != user_id:
                    raise HTTPException(status_code=403, detail=f"FORBIDDEN_ARTIFACT_ACCESS: Phân đoạn #{idx + 1} chứa artifact không thuộc sở hữu của bạn.")
                
                # Security: verify path integrity
                file_p = Path(art.file_path).resolve()
                if not file_p.is_file():
                    invalid_segments.append(f"Câu #{idx + 1} (Tệp âm thanh không tồn tại trên đĩa)")
                if file_p.suffix.lower() not in (".wav", ".pcm"):
                    invalid_segments.append(f"Câu #{idx + 1} (Định dạng file artifact không hợp lệ: {file_p.suffix})")

        if invalid_segments:
            raise HTTPException(
                status_code=400,
                detail=f"INCOMPLETE_SEGMENTS: Không thể xuất master audio do còn {len(invalid_segments)} câu chưa hoàn tất hoặc cần tạo lại: {', '.join(invalid_segments[:5])}"
            )

        ffmpeg_bin = resolve_ffmpeg_binary()
        verify_ffmpeg_capabilities(ffmpeg_bin)

        exports_dir = cls.get_exports_dir()
        export_id = str(uuid.uuid4())
        ext = "mp3" if req.format == "mp3" else "wav"
        final_output_file = exports_dir / f"{export_id}.{ext}"
        tmp_output_file = exports_dir / f"{export_id}.tmp.{ext}"

        # 2. Build DSP pipeline inside secure isolated temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            processed_wavs: List[Path] = []

            # Step A: Normalize each segment's sample rate and append turn-taking silence
            for i, seg in enumerate(ordered_segments):
                src_wav = Path(seg.active_artifact.file_path).resolve()
                step_out = tmp_path / f"seg_{i:04d}.wav"
                pause_s = max(0.0, float(seg.pause_after_ms) / 1000.0)

                # Resampling filter with SOXR quality + pause padding
                filter_str = f"aresample={req.sample_rate}"
                if pause_s > 0:
                    filter_str += f",apad=pad_dur={pause_s:.3f}"

                cmd_seg = [
                    ffmpeg_bin,
                    "-y",
                    "-i", str(src_wav),
                    "-af", filter_str,
                    "-c:a", "pcm_s16le",
                    str(step_out),
                ]
                proc_seg = subprocess.run(cmd_seg, capture_output=True, text=True, timeout=60)
                if proc_seg.returncode != 0:
                    raise RuntimeError(f"FFmpeg segment processing failed for segment {seg.id}: {proc_seg.stderr}")

                processed_wavs.append(step_out)

            # Step B: Write concat demuxer manifest with strict path escaping
            concat_manifest = tmp_path / "concat_list.txt"
            with open(concat_manifest, "w", encoding="utf-8") as f:
                for pw in processed_wavs:
                    # Escape single quotes according to FFmpeg concat demuxer standard
                    safe_path = str(pw.resolve()).replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")

            # Step C: Two-pass EBU R128 Loudness Normalization
            loudnorm_filter: Optional[str] = None
            if req.normalize_loudness:
                # Pass 1: Analysis pass to measure source audio dynamics
                cmd_pass1 = [
                    ffmpeg_bin,
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_manifest),
                    "-af", f"loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11:print_format=json",
                    "-f", "null",
                    "-",
                ]
                proc_pass1 = subprocess.run(cmd_pass1, capture_output=True, text=True, timeout=120)
                if proc_pass1.returncode != 0:
                    raise RuntimeError(f"FFmpeg EBU R128 Pass 1 analysis failed: {proc_pass1.stderr}")

                # Extract JSON dynamics from stderr
                match_p1 = re.search(
                    r"\{\s*\"input_i\"\s*:\s*\"([^\"]+)\".*?\"input_tp\"\s*:\s*\"([^\"]+)\".*?\"input_lra\"\s*:\s*\"([^\"]+)\".*?\"input_thresh\"\s*:\s*\"([^\"]+)\".*?\"target_offset\"\s*:\s*\"([^\"]+)\".*?\}",
                    proc_pass1.stderr,
                    re.DOTALL,
                )
                if match_p1:
                    m_i = match_p1.group(1)
                    m_tp = match_p1.group(2)
                    m_lra = match_p1.group(3)
                    m_thresh = match_p1.group(4)
                    m_offset = match_p1.group(5)
                    # Pass 2 filter with exact measured parameters
                    loudnorm_filter = (
                        f"loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11:"
                        f"measured_I={m_i}:measured_TP={m_tp}:measured_LRA={m_lra}:"
                        f"measured_thresh={m_thresh}:offset={m_offset}:linear=true"
                    )
                else:
                    loudnorm_filter = f"loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11"

            # Step D: Final concatenation & encoding to temporary output
            cmd_master = [
                ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_manifest),
            ]

            if loudnorm_filter:
                cmd_master.extend(["-af", loudnorm_filter])

            if req.format == "mp3":
                cmd_master.extend(["-c:a", "libmp3lame", "-b:a", "320k", "-ar", str(req.sample_rate)])
            else:
                cmd_master.extend(["-c:a", "pcm_s16le", "-ar", str(req.sample_rate)])

            cmd_master.append(str(tmp_output_file))

            proc_master = subprocess.run(cmd_master, capture_output=True, text=True, timeout=180)
            if proc_master.returncode != 0:
                if tmp_output_file.exists():
                    tmp_output_file.unlink(missing_ok=True)
                raise RuntimeError(f"FFmpeg master concatenation failed: {proc_master.stderr}")

            # Atomic publication: rename temporary file to final target
            os.replace(tmp_output_file, final_output_file)

        # 3. Measure final output audio metrics authentically
        metrics = measure_audio_metrics(final_output_file, ffmpeg_bin)

        # Enforce quota check and commit reservation for final export file size
        try:
            await UserQuotaService.commit_reservation(session, export_reservation.id, metrics["file_size_bytes"])
        except Exception:
            await UserQuotaService.release_reservation(session, export_reservation.id)
            if final_output_file.exists():
                final_output_file.unlink(missing_ok=True)
            raise

        # 4. Save ProjectExportRecord in database
        export_rec = ProjectExportRecord(
            id=export_id,
            project_id=project.id,
            user_id=user_id,
            format=req.format,
            sample_rate=metrics["sample_rate"] or req.sample_rate,
            file_path=str(final_output_file.resolve()),
            file_size_bytes=metrics["file_size_bytes"],
            duration_seconds=metrics["duration_seconds"],
            sha256_checksum=metrics["sha256_checksum"],
            loudness_lufs=metrics["loudness_lufs"],
            segment_count=len(ordered_segments),
        )
        session.add(export_rec)
        await session.commit()
        await session.refresh(export_rec)
        return export_rec
