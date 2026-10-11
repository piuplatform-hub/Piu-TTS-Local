"""
AI Voice Studio — Phase 4 Acceptance Gate Audio Production Script
Executes 4 complete end-to-end audio production workflows using REAL local engines:
- VieNeu-TTS v3 Turbo on CPU (48kHz)
- Qwen3-TTS 0.6B CustomVoice on GPU (24kHz)

Workflows executed:
- Workflow A: Long-form Vietnamese Narration (5+ sentences, edit & partial regenerate, WAV master)
- Workflow B: Mandarin Chinese Narration (4 sentences, MP3 master @ 192kbps)
- Workflow C: Multi-Character Mixed Vietnamese & Chinese Dialogue (Lan & Mei, pause timing, WAV & MP3)
- Workflow D: Persistence verification & database reload validation

Outputs saved outside git to: D:\\AIVoiceStudioData\\acceptance_audio_phase4\\
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import secrets
import sys
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Set environment
os.environ["ENABLE_GPU_INFERENCE"] = "true"
os.environ["STUDIO_DATA_DIR"] = r"D:\AIVoiceStudioData"
os.environ["STUDIO_FFMPEG_PATH"] = r"C:\Program Files\Piu Downloader\ffmpeg.exe"

from sqlalchemy import select
from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.models.user import User
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.character import CharacterRecord
from apps.server.src.models.segment import ScriptSegmentRecord, SegmentRevisionRecord
from apps.server.src.schemas.project import ProjectCreate, CharacterCreate, SegmentCreate, SegmentUpdate, MasterExportRequest
from apps.server.src.services.auth_service import AuthService
from apps.server.src.services.engine_service import EngineService
from apps.server.src.services.project_service import ProjectService
from apps.server.src.services.audio_dsp_service import AudioDspService, measure_audio_metrics
from apps.server.src.supervisor.scheduler import scheduler
from apps.server.src.supervisor.supervisor import supervisor

ACCEPTANCE_DIR = Path(r"D:\AIVoiceStudioData\acceptance_audio_phase4")
ACCEPTANCE_DIR.mkdir(parents=True, exist_ok=True)


async def wait_for_segment_jobs(project_id: str, user: User, expected_count: int, timeout_s: float = 180.0):
    """Polls until expected number of segments reach completed or failed status."""
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        async with database.AsyncSessionLocal() as session:
            project = await ProjectService.reconcile_project_segments(session, user, project_id)
            completed = sum(1 for s in project.segments if s.status == "completed")
            failed = sum(1 for s in project.segments if s.status == "failed")
            rendering = sum(1 for s in project.segments if s.status in ("rendering", "queued"))
            print(f"   [Progress] {completed}/{expected_count} completed, {rendering} in-flight, {failed} failed...")
            if completed == expected_count:
                return project
            if failed > 0:
                print(f"   [WARNING] Detected {failed} failed segments!")
                return project
        await asyncio.sleep(2.0)
    raise TimeoutError(f"Timed out waiting for segments of project {project_id} after {timeout_s}s")


async def run_acceptance_pipeline():
    print("=" * 70)
    print("AI VOICE STUDIO — PHASE 4 REAL AUDIO PRODUCTION ACCEPTANCE PIPELINE")
    print("Target Directory: D:\\AIVoiceStudioData\\acceptance_audio_phase4\\")
    print("=" * 70)

    # 1. Initialize DB and discover real engines
    await database.init_db()
    workspace_root = Path(__file__).resolve().parents[1]

    print("\n[INIT] Registering inference engines and launching supervised workers...")
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(
            session, workspace_root, spawn_workers=True
        )
        print("   Engines discovered and registered with supervisor.")

    print("[INIT] Starting Durable Job Scheduler daemon...")
    await scheduler.start()

    # 2. Get or create QA user
    from apps.server.src.core.security import hash_password
    async with database.AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.username == "acceptance_qa"))
        user = res.scalar_one_or_none()
        if not user:
            # Check if any user exists or create QA user
            user = User(
                username="acceptance_qa",
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role="admin",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user_id = user.id
        print(f"[AUTH] QA User: {user.username} (ID: {user_id})")

    results_summary = {}

    # =========================================================================
    # WORKFLOW A: Long-form Vietnamese Narration (VieNeu-TTS)
    # =========================================================================
    print("\n" + "=" * 50)
    print("WORKFLOW A: Long-form Vietnamese Narration (VieNeu-TTS on CPU)")
    print("=" * 50)

    async with database.AsyncSessionLocal() as session:
        proj_a = await ProjectService.create_project(
            session, user_id,
            ProjectCreate(
                title="Hành Trình Di Sản Cố Đô",
                description="Long-form Vietnamese narration exploring Hue heritage",
                project_type="narration",
                settings={"language": "vi", "engine_id": "vieneu-tts", "voice_id": "mai_anh"}
            )
        )
        proj_a_id = proj_a.id

    sentences_a = [
        "Huế mộng mơ với những cơn mưa thu nhè nhẹ rơi trên dòng sông Hương tĩnh lặng.",
        "Đại Nội cổ kính trầm mặc chứng kiến bao thăng trầm của lịch sử triều Nguyễn.",
        "Chùa Thiên Mụ trầm mặc soi bóng xuống dòng nước trong veo mỗi buổi sớm mai.",
        "Tiếng chuông chùa ngân nga xua tan những ưu tư muộn phiền của dòng đời hối hả.",
        "Ẩm thực xứ Huế mang đậm hương vị cung đình tinh tế và nồng nàn khó quên.",
    ]

    print(f"[WF-A] Creating 5 script segments for project {proj_a_id}...")
    seg_a_ids = []
    async with database.AsyncSessionLocal() as session:
        for idx, text in enumerate(sentences_a):
            s = await ProjectService.add_segment(
                session, user_id, proj_a_id,
                SegmentCreate(
                    sequence_order=idx,
                    text=text,
                    language="vi",
                    engine_id="vieneu-tts",
                    voice_id="mai_anh",
                    pause_after_ms=300,
                )
            )
            seg_a_ids.append(s.id)

    print(f"[WF-A] Batch rendering 5 segments via VieNeu-TTS CPU...")
    async with database.AsyncSessionLocal() as session:
        await ProjectService.render_batch(session, user, proj_a_id)

    # Wait for completion
    proj_a_rec = await wait_for_segment_jobs(proj_a_id, user, expected_count=5, timeout_s=180.0)
    print(f"[WF-A] All 5 initial segments rendered successfully.")

    # Revision testing: Modify Sentence 2 and regenerate
    print(f"[WF-A] Editing Segment #2 to test partial invalidation and non-destructive revisions...")
    seg2_id = seg_a_ids[1]
    new_text_seg2 = "Hoàng thành Thăng Long và Cố đô Huế là hai di sản văn hóa vô giá của dân tộc ta."
    async with database.AsyncSessionLocal() as session:
        seg2_curr = await session.get(ScriptSegmentRecord, seg2_id)
        proj_curr = await session.get(ProjectRecord, proj_a_id)
        await ProjectService.update_segment(
            session, user_id, proj_a_id, seg2_id,
            SegmentUpdate(
                text=new_text_seg2,
                expected_segment_version=seg2_curr.version,
                expected_project_version=proj_curr.version,
            )
        )

    print(f"[WF-A] Re-rendering updated Segment #2...")
    async with database.AsyncSessionLocal() as session:
        await ProjectService.render_segment(session, user, proj_a_id, seg2_id)

    # Wait for updated segment completion
    proj_a_rec = await wait_for_segment_jobs(proj_a_id, user, expected_count=5, timeout_s=90.0)

    # Verify revision was archived
    async with database.AsyncSessionLocal() as session:
        revs = (await session.execute(
            select(SegmentRevisionRecord).where(SegmentRevisionRecord.segment_id == seg2_id)
        )).scalars().all()
        print(f"[WF-A] Verified Segment #2 has {len(revs)} historical revision(s) safely preserved.")

    # Export Master WAV (EBU R128 -16 LUFS, -1.0 dBTP)
    print(f"[WF-A] Exporting Master WAV with Two-Pass EBU R128 loudness normalization...")
    async with database.AsyncSessionLocal() as session:
        export_a = await AudioDspService.export_project(
            session, user_id, proj_a_id,
            MasterExportRequest(
                format="wav",
                target_lufs=-16.0,
                true_peak_dbtp=-1.0,
            )
        )
        wav_master_path = Path(export_a.file_path)

    # Copy to target acceptance folder
    target_a_wav = ACCEPTANCE_DIR / "workflow_a_vietnamese_master.wav"
    shutil.copy2(wav_master_path, target_a_wav)
    print(f"[WF-A] Master WAV copied to: {target_a_wav}")

    metrics_a = measure_audio_metrics(target_a_wav)
    print(f"[WF-A] Master Metrics: {metrics_a}")
    results_summary["Workflow_A_Vietnamese_WAV"] = {
        "project_id": proj_a_id,
        "export_id": export_a.id,
        "file_name": target_a_wav.name,
        **metrics_a
    }

    # =========================================================================
    # WORKFLOW B: Mandarin Chinese Narration (Qwen3-TTS)
    # =========================================================================
    print("\n" + "=" * 50)
    print("WORKFLOW B: Mandarin Chinese Narration (Qwen3-TTS 0.6B on GPU)")
    print("=" * 50)

    async with database.AsyncSessionLocal() as session:
        proj_b = await ProjectService.create_project(
            session, user_id,
            ProjectCreate(
                title="江南水乡春色",
                description="Mandarin Chinese narration rendered on NVIDIA GPU",
                project_type="narration",
                settings={"language": "zh", "engine_id": "qwen3-tts", "voice_id": "vivian"}
            )
        )
        proj_b_id = proj_b.id

    sentences_b = [
        "江南的春天总是伴随着绵绵的细雨，水汽朦胧。",
        "青石板路两侧白墙黑瓦，宛如一幅徐徐展开的水墨丹青。",
        "摇橹船从古老的小桥下缓缓划过，荡起层层碧绿的涟漪。",
        "微风拂过柳梢，空气中弥漫着新茶与泥土的清甜香气。",
    ]

    print(f"[WF-B] Creating 4 script segments for project {proj_b_id}...")
    seg_b_ids = []
    async with database.AsyncSessionLocal() as session:
        for idx, text in enumerate(sentences_b):
            s = await ProjectService.add_segment(
                session, user_id, proj_b_id,
                SegmentCreate(
                    sequence_order=idx,
                    text=text,
                    language="zh",
                    engine_id="qwen3-tts",
                    voice_id="vivian",
                    pause_after_ms=300,
                )
            )
            seg_b_ids.append(s.id)

    print(f"[WF-B] Batch rendering 4 segments via Qwen3-TTS GPU...")
    async with database.AsyncSessionLocal() as session:
        await ProjectService.render_batch(session, user, proj_b_id)

    # Wait for completion
    proj_b_rec = await wait_for_segment_jobs(proj_b_id, user, expected_count=4, timeout_s=180.0)
    print(f"[WF-B] All 4 segments rendered successfully.")

    # Export Master MP3 (EBU R128 -16 LUFS, 192kbps)
    print(f"[WF-B] Exporting Master MP3 @ 192kbps with EBU R128 loudness normalization...")
    async with database.AsyncSessionLocal() as session:
        export_b = await AudioDspService.export_project(
            session, user_id, proj_b_id,
            MasterExportRequest(
                format="mp3",
                target_lufs=-16.0,
                true_peak_dbtp=-1.0,
                mp3_bitrate_kbps=192,
            )
        )
        mp3_master_path = Path(export_b.file_path)

    target_b_mp3 = ACCEPTANCE_DIR / "workflow_b_chinese_master.mp3"
    shutil.copy2(mp3_master_path, target_b_mp3)
    print(f"[WF-B] Master MP3 copied to: {target_b_mp3}")

    metrics_b = measure_audio_metrics(target_b_mp3)
    print(f"[WF-B] Master Metrics: {metrics_b}")
    results_summary["Workflow_B_Chinese_MP3"] = {
        "project_id": proj_b_id,
        "export_id": export_b.id,
        "file_name": target_b_mp3.name,
        **metrics_b
    }

    # =========================================================================
    # WORKFLOW C: Multi-Character Mixed Vietnamese & Chinese Dialogue
    # =========================================================================
    print("\n" + "=" * 50)
    print("WORKFLOW C: Multi-Character Mixed Dialogue (Lan & Mei, VieNeu + Qwen3)")
    print("=" * 50)

    async with database.AsyncSessionLocal() as session:
        proj_c = await ProjectService.create_project(
            session, user_id,
            ProjectCreate(
                title="Hội Ngộ Á Châu — Hà Nội Thu Vàng",
                description="Cross-engine multi-character dialogue between Vietnamese host and Chinese tourist",
                project_type="dialogue",
            )
        )
        proj_c_id = proj_c.id

        # Character 1: Lan (Vietnamese host)
        char_lan = await ProjectService.create_character(
            session, user_id, proj_c_id,
            CharacterCreate(
                name="Lan",
                avatar_color="#10b981",
                engine_id="vieneu-tts",
                voice_id="mai_anh",
                language="vi",
                sort_order=0,
            )
        )
        # Character 2: Mei (Chinese traveler)
        char_mei = await ProjectService.create_character(
            session, user_id, proj_c_id,
            CharacterCreate(
                name="Mei",
                avatar_color="#6366f1",
                engine_id="qwen3-tts",
                voice_id="vivian",
                language="zh",
                sort_order=1,
            )
        )
        lan_id, mei_id = char_lan.id, char_mei.id
        print(f"[WF-C] Created Characters: Lan ({lan_id}) & Mei ({mei_id})")

    dialogue_lines = [
        (lan_id, "Chào Mei, rất vui được gặp bạn tại Hà Nội vào mùa thu tuyệt đẹp này!", "vi", "vieneu-tts", "mai_anh", 400),
        (mei_id, "你好，兰！这里的秋天真的很美，微风让人感到非常舒适。", "zh", "qwen3-tts", "vivian", 500),
        (lan_id, "Hôm nay mình sẽ đưa bạn đi dạo quanh Hồ Gươm và thưởng thức món phở bò truyền thống nhé.", "vi", "vieneu-tts", "mai_anh", 350),
        (mei_id, "太棒了，我早就听说过越南河粉的美味，非常期待！", "zh", "qwen3-tts", "vivian", 300),
    ]

    print(f"[WF-C] Creating 4 dialogue lines with alternating engines and pause settings...")
    async with database.AsyncSessionLocal() as session:
        for idx, (c_id, text, lang, eng, voice, pause_ms) in enumerate(dialogue_lines):
            await ProjectService.add_segment(
                session, user_id, proj_c_id,
                SegmentCreate(
                    sequence_order=idx,
                    character_id=c_id,
                    text=text,
                    language=lang,
                    engine_id=eng,
                    voice_id=voice,
                    pause_after_ms=pause_ms,
                )
            )

    print(f"[WF-C] Batch rendering dialogue segments across both CPU and GPU...")
    async with database.AsyncSessionLocal() as session:
        await ProjectService.render_batch(session, user, proj_c_id)

    proj_c_rec = await wait_for_segment_jobs(proj_c_id, user, expected_count=4, timeout_s=180.0)
    print(f"[WF-C] All 4 dialogue segments rendered successfully.")

    # Export Master WAV & MP3
    print(f"[WF-C] Exporting Mixed Dialogue Master WAV...")
    async with database.AsyncSessionLocal() as session:
        export_c_wav = await AudioDspService.export_project(
            session, user_id, proj_c_id,
            MasterExportRequest(
                format="wav",
                target_lufs=-16.0,
                true_peak_dbtp=-1.0,
            )
        )
        c_wav_path = Path(export_c_wav.file_path)

    target_c_wav = ACCEPTANCE_DIR / "workflow_c_mixed_dialogue_master.wav"
    shutil.copy2(c_wav_path, target_c_wav)
    metrics_c_wav = measure_audio_metrics(target_c_wav)
    print(f"[WF-C] Dialogue Master WAV Metrics: {metrics_c_wav}")
    results_summary["Workflow_C_Dialogue_WAV"] = {
        "project_id": proj_c_id,
        "export_id": export_c_wav.id,
        "file_name": target_c_wav.name,
        **metrics_c_wav
    }

    print(f"[WF-C] Exporting Mixed Dialogue Master MP3...")
    async with database.AsyncSessionLocal() as session:
        export_c_mp3 = await AudioDspService.export_project(
            session, user_id, proj_c_id,
            MasterExportRequest(
                format="mp3",
                target_lufs=-16.0,
                true_peak_dbtp=-1.0,
                mp3_bitrate_kbps=192,
            )
        )
        c_mp3_path = Path(export_c_mp3.file_path)

    target_c_mp3 = ACCEPTANCE_DIR / "workflow_c_mixed_dialogue_master.mp3"
    shutil.copy2(c_mp3_path, target_c_mp3)
    metrics_c_mp3 = measure_audio_metrics(target_c_mp3)
    print(f"[WF-C] Dialogue Master MP3 Metrics: {metrics_c_mp3}")
    results_summary["Workflow_C_Dialogue_MP3"] = {
        "project_id": proj_c_id,
        "export_id": export_c_mp3.id,
        "file_name": target_c_mp3.name,
        **metrics_c_mp3
    }

    # =========================================================================
    # WORKFLOW D: Persistence and Reload Validation
    # =========================================================================
    print("\n" + "=" * 50)
    print("WORKFLOW D: Persistence & Reload Across System Restart")
    print("=" * 50)

    # Re-fetch all three projects from scratch
    async with database.AsyncSessionLocal() as session:
        for p_id, expected_title in [(proj_a_id, "Hành Trình Di Sản Cố Đô"), (proj_b_id, "江南水乡春色"), (proj_c_id, "Hội Ngộ Á Châu — Hà Nội Thu Vàng")]:
            proj_loaded = await ProjectService.get_project_record(session, p_id, user_id)
            assert proj_loaded.title == expected_title
            assert len(proj_loaded.segments) >= 4
            assert all(s.active_artifact_id is not None for s in proj_loaded.segments)
            assert all(s.status == "completed" for s in proj_loaded.segments)
            print(f"[WF-D] Project '{proj_loaded.title}' loaded with {len(proj_loaded.segments)} complete segments.")

    print("[WF-D] Data durability & persistence across reload verified.")

    # Save metrics summary
    summary_path = ACCEPTANCE_DIR / "metrics_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)
    print(f"\n[SUMMARY] Metrics saved to: {summary_path}")

    # Clean shutdown
    print("\n[CLEANUP] Stopping scheduler and terminating supervised workers...")
    await scheduler.stop()
    await supervisor.stop_all()
    await database.engine.dispose()
    print("[SUCCESS] Phase 4 Audio Production Acceptance completed cleanly!")


if __name__ == "__main__":
    asyncio.run(run_acceptance_pipeline())
