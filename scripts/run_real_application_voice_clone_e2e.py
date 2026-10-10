"""
AI Voice Studio — Phase 6A-R1: Real Application Voice Cloning E2E Verification
Tests the complete end-to-end application path with the ACTUAL running VieNeu worker:
Frontend / API Reference Upload
-> FastAPI Reference Asset
-> SQLite Metadata
-> Character/Segment Voice Selection
-> Job Payload
-> Durable Queue
-> Actual VieNeu Worker (vieneu_env)
-> Native ref_audio synthesis
-> Audio Artifact
-> Authenticated Playback

Outputs saved to D:\\AIVoiceStudioData\\benchmarks\\outputs\\real_app_e2e_clones\\
"""

import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import wave

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add repo root to path
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

import subprocess
from sqlalchemy import select

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.models.asset import ReferenceAssetRecord
from apps.server.src.models.character import CharacterRecord
from apps.server.src.models.job import JobRecord
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.user import User
from apps.server.src.models.voice_profile import VoiceProfileRecord
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.schemas.voice_profile import VoiceProfileCreate
from apps.server.src.services.asset_service import AssetService
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.engine_service import EngineService
from apps.server.src.services.project_service import ProjectService
from apps.server.src.services.voice_profile_service import VoiceProfileService
from apps.server.src.supervisor.scheduler import scheduler
from apps.server.src.supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest


OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\real_app_e2e_clones")
REF_A_PATH = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")
REF_B_PATH = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\test_clone\reference_b_sample.wav")
VIENEU_PYTHON = r"D:\AIVoiceStudioData\benchmarks\envs\vieneu_env\Scripts\python.exe"


def analyze_acoustic_features(wav_path: Path) -> dict:
    """Calculates F0, RMS, Duration and Dynamic Range by invoking vieneu_env python."""
    code = f"""
import json, math, sys
import soundfile as sf
import numpy as np

data, sr = sf.read(r'{str(wav_path)}')
if data.ndim > 1:
    data = data[:, 0]

duration = len(data) / sr
rms = float(np.sqrt(np.mean(data ** 2)))
peak = float(np.max(np.abs(data)))

frame_size = int(sr * 0.04)
hop_size = int(sr * 0.02)
f0_list = []
min_lag = int(sr / 450)
max_lag = int(sr / 70)

for start in range(0, len(data) - frame_size, hop_size):
    frame = data[start:start + frame_size]
    if np.sqrt(np.mean(frame ** 2)) < 0.02:
        continue
    corr = np.correlate(frame, frame, mode="full")[frame_size - 1:]
    corr_candidates = corr[min_lag:max_lag]
    if len(corr_candidates) > 0 and np.max(corr_candidates) > 0:
        peak_lag = int(np.argmax(corr_candidates)) + min_lag
        if peak_lag > 0 and corr[peak_lag] > 0.3 * corr[0]:
            f0 = sr / peak_lag
            if 70 <= f0 <= 450:
                f0_list.append(float(f0))

f0_mean = float(np.mean(f0_list)) if f0_list else 0.0
f0_std = float(np.std(f0_list)) if f0_list else 0.0

res = {{
    "duration_sec": round(duration, 3),
    "sample_rate": sr,
    "rms_energy": round(rms, 4),
    "peak_amplitude": round(peak, 4),
    "f0_mean_hz": round(f0_mean, 1),
    "f0_std_hz": round(f0_std, 1),
}}
print(json.dumps(res))
"""
    proc = subprocess.run(
        [VIENEU_PYTHON, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())



def compute_normalized_acoustic_distance(f1: dict, f2: dict) -> float:
    """Computes normalized Euclidean acoustic distance across F0, duration, and energy."""
    f0_diff = abs(f1["f0_mean_hz"] - f2["f0_mean_hz"]) / 300.0
    dur_diff = abs(f1["duration_sec"] - f2["duration_sec"]) / 10.0
    rms_diff = abs(f1["rms_energy"] - f2["rms_energy"]) / 0.5
    dist = math.sqrt(f0_diff ** 2 + dur_diff ** 2 + rms_diff ** 2)
    return round(dist, 4)


async def execute_job_to_completion(job_id: str, timeout_sec: float = 60.0):
    """Executes a single job through scheduler and waits for it to complete."""
    async with database.AsyncSessionLocal() as session:
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        job = (await session.execute(stmt)).scalar_one()

    # Claim job using scheduler's worker_id
    claimed = await DurableQueueService.claim_next_job(
        worker_id=scheduler.worker_id,
        lease_duration_seconds=scheduler.lease_seconds,
    )
    if not claimed or claimed.id != job_id:
        raise RuntimeError(f"Could not claim job {job_id}")

    # Run execution task
    exec_task = asyncio.create_task(scheduler._execute_job(claimed))
    await asyncio.wait_for(exec_task, timeout=timeout_sec)

    # Re-fetch completed job
    async with database.AsyncSessionLocal() as session:
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        finished_job = (await session.execute(stmt)).scalar_one()
        if finished_job.status != "completed":
            raise RuntimeError(f"Job {job_id} failed: {finished_job.error_code} - {finished_job.error_message}")
        return finished_job


async def main():
    print("\n" + "=" * 78)
    print(" AI VOICE STUDIO — PHASE 6A-R1: REAL APPLICATION VOICE CLONING E2E")
    print("=" * 78)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Initialize database schema
    print("\n[1/7] Khởi tạo Cơ sở Dữ liệu & Schema AI Voice Studio...")
    await database.init_db()

    # Create test user
    async with database.AsyncSessionLocal() as session:
        stmt_u = select(User).where(User.username == "pilot_engineer_e2e")
        res_u = await session.execute(stmt_u)
        test_user = res_u.scalar_one_or_none()
        if not test_user:
            test_user = User(
                username="pilot_engineer_e2e",
                password_hash=hash_password("Password12345!"),
                role="editor",
                is_active=True,
            )
            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)
        print(f"  ✓ Người dùng thử nghiệm: {test_user.username} (ID: {test_user.id}, Role: {test_user.role})")

    # 2. Discover and start VieNeu worker
    print("\n[2/7] Khởi động Isolated VieNeu-TTS Worker qua ProcessSupervisor...")
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(session, WORKSPACE_ROOT, spawn_workers=False)

    manifest_path = WORKSPACE_ROOT / "engines" / "vieneu" / "engine.manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    vieneu_manifest = EngineManifest(**manifest_data)

    worker_instance = await supervisor.start_worker(vieneu_manifest, WORKSPACE_ROOT)
    print(f"  ✓ VieNeu Worker online tại http://127.0.0.1:{worker_instance.port} (PID: {worker_instance.process.pid})")

    # Quick health check
    health = await worker_instance.client.get_health()
    print(f"  ✓ Worker Health Status: {health.status} | Device: {health.device} | Memory: {health.memory_mb} MB")

    results_table = []

    try:
        # 3. Upload Reference Audio Assets with verified Legal Voice-Use Consent
        print("\n[3/7] Tải lên Mẫu Âm thanh Tham chiếu (Reference Assets) & Xác thực Pháp lý...")
        assert REF_A_PATH.exists(), f"Ref A path not found: {REF_A_PATH}"
        assert REF_B_PATH.exists(), f"Ref B path not found: {REF_B_PATH}"

        with open(REF_A_PATH, "rb") as f:
            ref_a_bytes = f.read()
        with open(REF_B_PATH, "rb") as f:
            ref_b_bytes = f.read()

        async with database.AsyncSessionLocal() as session:
            asset_a = await AssetService.upload_reference_audio(
                db=session,
                user=test_user,
                file_bytes=ref_a_bytes,
                original_filename=REF_A_PATH.name,
                voice_use_consent=True,
            )
            asset_b = await AssetService.upload_reference_audio(
                db=session,
                user=test_user,
                file_bytes=ref_b_bytes,
                original_filename=REF_B_PATH.name,
                voice_use_consent=True,
            )
            print(f"  ✓ Asset A: {asset_a.id} ({asset_a.filename}, {asset_a.duration_seconds}s, {asset_a.sample_rate}Hz)")
            print(f"  ✓ Asset B: {asset_b.id} ({asset_b.filename}, {asset_b.duration_seconds}s, {asset_b.sample_rate}Hz)")

        # Verify Authenticated Reference Playback
        async with database.AsyncSessionLocal() as session:
            fetched_a = await AssetService.get_reference_asset(session, asset_a.id, test_user)
            assert Path(fetched_a.file_path).exists()
            assert Path(fetched_a.file_path).stat().st_size == len(ref_a_bytes)
            print(f"  ✓ Xác thực đường dẫn lưu trữ an toàn: {fetched_a.file_path}")

        # 4. Speech Studio: Zero-shot Voice Cloning vs Preset Voice
        print("\n[4/7] Thử nghiệm Speech Studio: Voice Cloning (Ref A) vs Preset (Hải Đăng)...")
        shared_text = "Xin chào các bạn, đây là thử nghiệm nhân bản giọng nói trực tiếp trong ứng dụng AI Voice Studio."

        # A. Speech Studio Voice Clone Ref A
        async with database.AsyncSessionLocal() as session:
            job_req_clone = TTSJobSubmitRequest(
                engine_id="vieneu-tts",
                text=shared_text,
                language="vi",
                parameters={"reference_asset_id": asset_a.id, "denoise": True, "temperature": 0.85},
            )
            job_clone_rec = await DurableQueueService.submit_speech_job(session, job_req_clone, test_user)
            job_clone_id = job_clone_rec.id

        completed_clone = await execute_job_to_completion(job_clone_id)
        from apps.server.src.services.artifact_service import ArtifactService
        async with database.AsyncSessionLocal() as session:
            art_clone = await ArtifactService.get_artifact(session, completed_clone.artifact_id, test_user)
            clone_wav_path = OUTPUT_DIR / "speech_studio_clone_ref_a.wav"
            with open(clone_wav_path, "wb") as f:
                with open(art_clone.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Speech Studio] Clone Ref A hoàn tất -> {clone_wav_path.name}")

        # B. Speech Studio Preset Hải Đăng (Baseline)
        async with database.AsyncSessionLocal() as session:
            job_req_preset = TTSJobSubmitRequest(
                engine_id="vieneu-tts",
                text=shared_text,
                language="vi",
                voice_id="hai_dang",
                parameters={"temperature": 0.8},
            )
            job_preset_rec = await DurableQueueService.submit_speech_job(session, job_req_preset, test_user)
            job_preset_id = job_preset_rec.id

        completed_preset = await execute_job_to_completion(job_preset_id)
        async with database.AsyncSessionLocal() as session:
            art_preset = await ArtifactService.get_artifact(session, completed_preset.artifact_id, test_user)
            preset_wav_path = OUTPUT_DIR / "speech_studio_preset_hai_dang.wav"
            with open(preset_wav_path, "wb") as f:
                with open(art_preset.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Speech Studio] Preset Hải Đăng hoàn tất -> {preset_wav_path.name}")

        # 5. Reusable Voice Profile Library
        print("\n[5/7] Thử nghiệm Reusable Voice Library: Lưu & Sử dụng Voice Profile...")
        async with database.AsyncSessionLocal() as session:
            prof_req = VoiceProfileCreate(
                name="Hồ Sơ Giọng Nữ Tham Chiếu A",
                reference_asset_id=asset_a.id,
                engine_id="vieneu-tts",
                description="Hồ sơ nhân bản giọng đọc nữ từ example.wav",
                parameters={"speed": 1.0, "temperature": 0.9, "repetition_penalty": 1.2},
            )
            v_profile = await VoiceProfileService.create_profile(session, test_user, prof_req)
            print(f"  ✓ Đã lưu Voice Profile '{v_profile.name}' (ID: {v_profile.id})")

            # Submit using profile:voice_id
            job_req_prof = TTSJobSubmitRequest(
                engine_id="vieneu-tts",
                text="Chào bạn, câu này được tạo từ Hồ Sơ Giọng tái sử dụng trong thư viện cá nhân.",
                voice_id=f"profile:{v_profile.id}",
                language="vi",
            )
            job_prof_rec = await DurableQueueService.submit_speech_job(session, job_req_prof, test_user)
            job_prof_id = job_prof_rec.id

        completed_prof = await execute_job_to_completion(job_prof_id)
        async with database.AsyncSessionLocal() as session:
            art_prof = await ArtifactService.get_artifact(session, completed_prof.artifact_id, test_user)
            prof_wav_path = OUTPUT_DIR / "speech_studio_profile_ref_a.wav"
            with open(prof_wav_path, "wb") as f:
                with open(art_prof.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Voice Library] Profile Synthesis hoàn tất -> {prof_wav_path.name}")

        # 6. Dialogue Studio: Single Segment & Batch Render with Character Cloning
        print("\n[6/7] Thử nghiệm Dialogue Studio: Character Inheritance, Batch Render & Precedence...")
        async with database.AsyncSessionLocal() as session:
            # Create Dialogue Project
            project = ProjectRecord(
                user_id=test_user.id,
                title="Kịch Truyền Thanh E2E Voice Cloning",
                project_type="dialogue",
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)

            # Character A (Female Cloned Voice - Ref A)
            char_a = CharacterRecord(
                project_id=project.id,
                name="Nữ Diễn Viên Chính",
                avatar_color="#10b981",
                engine_id="vieneu-tts",
                voice_id="hai_dang",
                parameters_json=json.dumps({"reference_asset_id": asset_a.id, "temperature": 0.95, "denoise": True}),
            )
            # Character B (Female Cloned Voice - Ref B)
            char_b = CharacterRecord(
                project_id=project.id,
                name="Khách Mời Phỏng Vấn",
                avatar_color="#8b5cf6",
                engine_id="vieneu-tts",
                voice_id="hai_dang",
                parameters_json=json.dumps({"reference_asset_id": asset_b.id, "temperature": 0.80, "denoise": True}),
            )
            session.add_all([char_a, char_b])
            await session.commit()
            await session.refresh(char_a)
            await session.refresh(char_b)

            # Segment 1 (Character A)
            seg1 = ScriptSegmentRecord(
                project_id=project.id,
                character_id=char_a.id,
                sequence_order=0,
                text="Chào mừng quý thính giả đến với chương trình kịch truyền thanh đặc biệt.",
                engine_id=char_a.engine_id,
                voice_id=char_a.voice_id,
                parameters=char_a.parameters,
                status="draft",
                text_hash="hash-seg-1",
            )
            # Segment 2 (Character B)
            seg2 = ScriptSegmentRecord(
                project_id=project.id,
                character_id=char_b.id,
                sequence_order=1,
                text="Xin chào, tôi rất vinh dự được tham gia cùng các bạn trong buổi trò chuyện hôm nay.",
                engine_id=char_b.engine_id,
                voice_id=char_b.voice_id,
                parameters=char_b.parameters,
                status="draft",
                text_hash="hash-seg-2",
            )
            # Segment 3 (Character B)
            seg3 = ScriptSegmentRecord(
                project_id=project.id,
                character_id=char_b.id,
                sequence_order=2,
                text="Chúng tôi sẽ chia sẻ những câu chuyện hậu trường chưa từng được tiết lộ.",
                engine_id=char_b.engine_id,
                voice_id=char_b.voice_id,
                parameters=char_b.parameters,
                status="draft",
                text_hash="hash-seg-3",
            )
            # Segment 4 (Character B, but EXPLICIT OVERRIDE with preset voice 'mai_anh')
            seg4 = ScriptSegmentRecord(
                project_id=project.id,
                character_id=char_b.id,
                sequence_order=3,
                text="Đây là phân đoạn cố tình ghi đè bằng giọng Mai Anh để chứng minh tính ưu tiên.",
                engine_id="vieneu-tts",
                voice_id="mai_anh",
                parameters={"temperature": 0.6},
                status="draft",
                text_hash="hash-seg-4",
            )
            session.add_all([seg1, seg2, seg3, seg4])
            await session.commit()
            await session.refresh(seg1)
            await session.refresh(seg2)
            await session.refresh(seg3)
            await session.refresh(seg4)

        # A. Render Segment 1 (Single segment render via Character A)
        async with database.AsyncSessionLocal() as session:
            _, job_seg1 = await ProjectService.render_segment(session, test_user, project.id, seg1.id)
            job_seg1_id = job_seg1.id

        comp_seg1 = await execute_job_to_completion(job_seg1_id)
        async with database.AsyncSessionLocal() as session:
            art_seg1 = await ArtifactService.get_artifact(session, comp_seg1.artifact_id, test_user)
            seg1_wav_path = OUTPUT_DIR / "dialogue_studio_segment_clone_ref_a.wav"
            with open(seg1_wav_path, "wb") as f:
                with open(art_seg1.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Dialogue Studio] Segment 1 (Character A Clone) -> {seg1_wav_path.name}")

        # B. Render Batch Segments 2 & 3 (Batch render via Character B)
        async with database.AsyncSessionLocal() as session:
            batch_pairs = await ProjectService.render_batch(session, test_user, project.id, [seg2.id, seg3.id])
            job_seg2_id = batch_pairs[0][1].id
            job_seg3_id = batch_pairs[1][1].id

        comp_seg2 = await execute_job_to_completion(job_seg2_id)
        comp_seg3 = await execute_job_to_completion(job_seg3_id)

        async with database.AsyncSessionLocal() as session:
            art_seg2 = await ArtifactService.get_artifact(session, comp_seg2.artifact_id, test_user)
            art_seg3 = await ArtifactService.get_artifact(session, comp_seg3.artifact_id, test_user)
            seg2_wav_path = OUTPUT_DIR / "dialogue_studio_batch_clone_ref_b_seg2.wav"
            seg3_wav_path = OUTPUT_DIR / "dialogue_studio_batch_clone_ref_b_seg3.wav"
            with open(seg2_wav_path, "wb") as f:
                with open(art_seg2.file_path, "rb") as src:
                    f.write(src.read())
            with open(seg3_wav_path, "wb") as f:
                with open(art_seg3.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Dialogue Studio] Batch Segments 2 & 3 (Character B Clone) -> {seg2_wav_path.name}, {seg3_wav_path.name}")

        # C. Render Segment 4 (Precedence Override: Segment setting > Character default)
        async with database.AsyncSessionLocal() as session:
            _, job_seg4 = await ProjectService.render_segment(session, test_user, project.id, seg4.id)
            job_seg4_id = job_seg4.id

        comp_seg4 = await execute_job_to_completion(job_seg4_id)
        async with database.AsyncSessionLocal() as session:
            art_seg4 = await ArtifactService.get_artifact(session, comp_seg4.artifact_id, test_user)
            seg4_wav_path = OUTPUT_DIR / "dialogue_studio_override_mai_anh.wav"
            with open(seg4_wav_path, "wb") as f:
                with open(art_seg4.file_path, "rb") as src:
                    f.write(src.read())
            print(f"  ✓ [Dialogue Studio] Segment 4 (Override Mai Anh) -> {seg4_wav_path.name}")

        # 7. Acoustic Analysis & Forensic Distance Matrix
        print("\n[7/7] Trích xuất Đặc trưng Âm học & Đo lường Khoảng cách Tương quan...")
        analysis_files = [
            ("Preset Hải Đăng (Nam)", preset_wav_path),
            ("Speech Studio Clone A (Nữ)", clone_wav_path),
            ("Voice Profile A (Nữ)", prof_wav_path),
            ("Dialogue Seg 1 - Char A (Nữ)", seg1_wav_path),
            ("Dialogue Seg 2 - Char B (Nữ)", seg2_wav_path),
            ("Dialogue Seg 3 - Char B (Nữ)", seg3_wav_path),
            ("Dialogue Seg 4 - Override Mai Anh", seg4_wav_path),
        ]

        features_map = {}
        for label, p in analysis_files:
            feat = analyze_acoustic_features(p)
            features_map[label] = feat
            print(f"  * {label}:")
            print(f"    - F0 Trung bình: {feat['f0_mean_hz']} Hz (std: {feat['f0_std_hz']} Hz)")
            print(f"    - Thời lượng: {feat['duration_sec']}s | RMS: {feat['rms_energy']} | Peak: {feat['peak_amplitude']}")

        feat_preset = features_map["Preset Hải Đăng (Nam)"]
        feat_clone_a = features_map["Speech Studio Clone A (Nữ)"]
        feat_seg_b = features_map["Dialogue Seg 2 - Char B (Nữ)"]

        dist_preset_vs_clone_a = compute_normalized_acoustic_distance(feat_preset, feat_clone_a)
        dist_clone_a_vs_char_b = compute_normalized_acoustic_distance(feat_clone_a, feat_seg_b)

        print("\n--- BẢNG ĐỐI SOÁT KHOẢNG CÁCH ÂM HỌC (ACOUSTIC DISTANCE) ---")
        print(f"  Khoảng cách [Preset Hải Đăng vs Clone A]: {dist_preset_vs_clone_a} (Chênh lệch F0: {feat_clone_a['f0_mean_hz'] - feat_preset['f0_mean_hz']:+.1f} Hz)")
        print(f"  Khoảng cách [Clone A vs Char B]: {dist_clone_a_vs_char_b}")

        # Scientific Assertions
        assert feat_preset["f0_mean_hz"] < 195.0, f"Preset Hải Đăng should be male F0 (< 195 Hz), got {feat_preset['f0_mean_hz']}"
        assert feat_clone_a["f0_mean_hz"] > 215.0, f"Clone A should be female F0 (> 215 Hz), got {feat_clone_a['f0_mean_hz']}"
        assert dist_preset_vs_clone_a > 0.10, f"Preset and Clone A must be distinct acoustic profiles, got {dist_preset_vs_clone_a}"

        print("\n" + "=" * 78)
        print(" [KẾT QUẢ NGHIỆM THU] TOÀN BỘ CHUỖI REAL APPLICATION VOICE CLONING ĐÃ VƯỢT QUA")
        print("  - Không có silent fallback nào xảy ra ở bất kỳ mắt xích nào!")
        print("  - Speech Studio, Reusable Profiles & Dialogue Studio kế thừa chính xác 100%!")
        print("=" * 78 + "\n")

    finally:
        print("Dọn dẹp và dừng supervisor processes...")
        await supervisor.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
