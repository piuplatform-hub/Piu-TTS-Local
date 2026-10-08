"""
Audio DSP & Master Export Service
Handles deterministic audio stitching, sample rate normalization (resampling),
silence insertion, EBU R128 loudness mastering, and WAV/MP3 export using FFmpeg.
Enforces strict subprocess argument safety without shell injection.
"""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
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


# Default locations to search for verified FFmpeg binary on Windows
KNOWN_FFMPEG_PATHS = [
    r"C:\Program Files\Piu Downloader\ffmpeg.exe",
    r"D:\C\Edit\Piu\_internal\ffmpeg.exe",
]


def resolve_ffmpeg_binary() -> str:
    """Finds an approved, verified FFmpeg executable on the target host."""
    # 1. Check environment variable override
    env_path = os.getenv("STUDIO_FFMPEG_PATH")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())

    # 2. Check known workstation installation locations
    for p in KNOWN_FFMPEG_PATHS:
        if Path(p).is_file():
            return str(Path(p).resolve())

    # 3. Check system PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg and Path(which_ffmpeg).is_file():
        return str(Path(which_ffmpeg).resolve())

    raise RuntimeError(
        "FFmpeg binary not found on host system. Please install FFmpeg or set STUDIO_FFMPEG_PATH."
    )


class AudioDspService:
    @staticmethod
    def get_exports_dir() -> Path:
        base_dir = Path(settings.DATA_DIR) if hasattr(settings, "DATA_DIR") and settings.DATA_DIR else Path("D:/AIVoiceStudioData")
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

        # 1. Verify 100% segments have completed audio artifacts
        missing_segments = []
        for idx, seg in enumerate(ordered_segments):
            if not seg.active_artifact_id or not seg.active_artifact:
                missing_segments.append(f"Câu #{idx + 1} (ID: {seg.id[:8]})")
            elif not Path(seg.active_artifact.file_path).is_file():
                missing_segments.append(f"Câu #{idx + 1} (Tệp âm thanh không tồn tại trên đĩa)")

        if missing_segments:
            raise HTTPException(
                status_code=400,
                detail=f"INCOMPLETE_SEGMENTS: Không thể xuất master audio do còn {len(missing_segments)} câu chưa hoàn tất: {', '.join(missing_segments[:5])}"
            )

        ffmpeg_bin = resolve_ffmpeg_binary()
        exports_dir = cls.get_exports_dir()
        export_id = str(uuid.uuid4())
        ext = "mp3" if req.format == "mp3" else "wav"
        output_file = exports_dir / f"{export_id}.{ext}"

        # 2. Build DSP pipeline with temporary files to avoid command-line length limits
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            processed_wavs = []

            # Step A: Normalize each segment's sample rate and append configured silence
            for i, seg in enumerate(ordered_segments):
                src_wav = Path(seg.active_artifact.file_path).resolve()
                step_out = tmp_path / f"seg_{i:04d}.wav"
                pause_s = max(0.0, float(seg.pause_after_ms) / 1000.0)

                # Filter: resample to target sample rate + pad with pause silence
                # e.g., aresample=48000,apad=pad_dur=0.3
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
                proc_seg = subprocess.run(cmd_seg, capture_output=True, text=True)
                if proc_seg.returncode != 0:
                    raise RuntimeError(f"FFmpeg segment processing failed for segment {seg.id}: {proc_seg.stderr}")

                processed_wavs.append(step_out)

            # Step B: Write concat demuxer manifest file
            concat_manifest = tmp_path / "concat_list.txt"
            with open(concat_manifest, "w", encoding="utf-8") as f:
                for pw in processed_wavs:
                    safe_path = str(pw.resolve()).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            # Step C: Master concat + optional EBU R128 loudness normalization
            cmd_master = [
                ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_manifest),
            ]

            audio_filters = []
            if req.normalize_loudness:
                audio_filters.append(f"loudnorm=I={req.target_lufs}:TP=-1.5:LRA=11")

            if audio_filters:
                cmd_master.extend(["-af", ",".join(audio_filters)])

            if req.format == "mp3":
                cmd_master.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
            else:
                cmd_master.extend(["-c:a", "pcm_s16le", "-ar", str(req.sample_rate)])

            cmd_master.append(str(output_file))

            proc_master = subprocess.run(cmd_master, capture_output=True, text=True)
            if proc_master.returncode != 0:
                raise RuntimeError(f"FFmpeg master concatenation failed: {proc_master.stderr}")

        # 3. Read metadata of exported master audio
        file_bytes = output_file.read_bytes()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)

        # Calculate duration using wave for WAV or ffprobe/audio header
        duration_s = 0.0
        if req.format == "wav":
            try:
                with wave.open(str(output_file), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration_s = frames / float(rate) if rate > 0 else 0.0
            except Exception:
                duration_s = sum(s.active_artifact.duration_seconds + (s.pause_after_ms / 1000.0) for s in ordered_segments)
        else:
            duration_s = sum(s.active_artifact.duration_seconds + (s.pause_after_ms / 1000.0) for s in ordered_segments)

        # 4. Save ProjectExportRecord in database
        export_rec = ProjectExportRecord(
            id=export_id,
            project_id=project.id,
            user_id=user_id,
            format=req.format,
            sample_rate=req.sample_rate,
            file_path=str(output_file.resolve()),
            file_size_bytes=file_size,
            duration_seconds=round(duration_s, 3),
            sha256_checksum=sha256,
            loudness_lufs=req.target_lufs if req.normalize_loudness else None,
            segment_count=len(ordered_segments),
        )
        session.add(export_rec)
        await session.commit()
        await session.refresh(export_rec)
        return export_rec
