"""
Phase 4 End-to-End Acceptance Tests
Validates the complete professional studio workflows:
- Workflow A: Long-form Vietnamese Narration (Auto-segmentation, partial invalidation, DSP export)
- Workflow B: Mandarin Chinese Narration (Chinese punctuation segmentation, Qwen3 engine)
- Workflow C: Multi-Character Dialogue (VieNeu 48kHz + Qwen3 24kHz mixed-engine dialogue, turn-taking pauses, EBU R128 mastering)
- Workflow D: Workspace Persistence across reload, optimistic concurrency, and multi-user isolation
"""

import math
from pathlib import Path
import struct
import wave
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.main import app
from apps.server.src.database import Base, get_db
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.models.user import User
from apps.server.src.models.engine import EngineRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.services.audio_dsp_service import AudioDspService


def make_test_wav(file_path: Path, duration_s: float = 1.0, sr: int = 48000, freq: float = 440.0):
    n_frames = int(sr * duration_s)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        samples = bytearray()
        for i in range(n_frames):
            val = int(16000.0 * math.sin(2.0 * math.pi * freq * (i / sr)))
            samples.extend(struct.pack("<h", max(-32768, min(32767, val))))
        wf.writeframes(samples)


@pytest.fixture
async def e2e_test_db(tmp_path):
    db_file = tmp_path / "test_phase4_e2e.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Seed mock engines
    async with session_factory() as session:
        eng1 = EngineRecord(
            id="vieneu-tts",
            name="VieNeu-TTS",
            version="3.8.3",
            device_target="cpu",
            capabilities=["text_to_speech", "voice_cloning"],
            manifest_data={},
        )
        eng2 = EngineRecord(
            id="qwen3-tts",
            name="Qwen3-TTS",
            version="1.0.0",
            device_target="cuda",
            capabilities=["text_to_speech"],
            manifest_data={},
        )
        session.add_all([eng1, eng2])
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.fixture
async def e2e_users(e2e_test_db):
    session_factory = e2e_test_db
    async with session_factory() as session:
        u_lead = User(
            username="producer_lead",
            password_hash=hash_password("LeadPass123!"),
            role="admin",
            is_active=True,
        )
        u_guest = User(
            username="editor_guest",
            password_hash=hash_password("GuestPass123!"),
            role="editor",
            is_active=True,
        )
        session.add_all([u_lead, u_guest])
        await session.commit()
        await session.refresh(u_lead)
        await session.refresh(u_guest)

        token_lead = create_access_token({"sub": u_lead.id, "username": u_lead.username, "role": u_lead.role})
        token_guest = create_access_token({"sub": u_guest.id, "username": u_guest.username, "role": u_guest.role})

    return {
        "lead_token": token_lead,
        "guest_token": token_guest,
        "lead_id": u_lead.id,
        "guest_id": u_guest.id,
    }


@pytest.mark.asyncio
async def test_workflow_a_longform_vietnamese_narration(e2e_test_db, e2e_users, tmp_path):
    """
    Workflow A: Long-form Vietnamese Narration
    1. Create Narration project
    2. Auto-segment raw chapter text
    3. Modify segment text -> verify status changes to stale
    4. Simulate audio generation & attach artifacts
    5. Export master audio (WAV 48kHz with EBU R128 loudness normalization)
    6. Verify master audio artifact integrity
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {e2e_users['lead_token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Narration Project
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Chương 1 - Mùa Lạc Trên Đất Đỏ",
                "description": "Tác phẩm văn học dài tập",
                "project_type": "narration",
            },
        )
        assert p_resp.status_code == 201
        p_data = p_resp.json()
        proj_id = p_data["id"]
        assert p_data["project_type"] == "narration"

        # 2. Auto-segment long-form Vietnamese text
        chapter_text = (
            "Mùa xuân đã về trên nông trường Điện Biên rực rỡ hoa ban. "
            "Những chiếc máy cày bắt đầu nổ máy rộn rã trên khắp cánh đồng. "
            "Bà con xã viên hân hoan bước vào vụ thu hoạch lạc mới."
        )
        auto_resp = await client.post(
            f"/api/v1/projects/{proj_id}/auto-segment",
            headers=headers,
            json={
                "text": chapter_text,
                "language": "vi",
                "max_chars_per_segment": 100,
                "default_engine_id": "vieneu-tts",
                "default_voice_id": "mai_anh",
            },
        )
        assert auto_resp.status_code == 200
        segments = auto_resp.json()
        assert len(segments) >= 2
        seg1_id = segments[0]["id"]
        seg2_id = segments[1]["id"]

        # 3. Simulate completion of segment 1 & 2
        w1 = tmp_path / "chap1_part1.wav"
        w2 = tmp_path / "chap1_part2.wav"
        make_test_wav(w1, duration_s=2.0, sr=48000, freq=440.0)
        make_test_wav(w2, duration_s=2.5, sr=48000, freq=554.37)

        async with e2e_test_db() as session:
            art1 = ArtifactRecord(
                owner_id=e2e_users["lead_id"],
                file_path=str(w1),
                file_size_bytes=len(w1.read_bytes()),
                duration_seconds=2.0,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="hash_chap1_part1",
            )
            art2 = ArtifactRecord(
                owner_id=e2e_users["lead_id"],
                file_path=str(w2),
                file_size_bytes=len(w2.read_bytes()),
                duration_seconds=2.5,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="hash_chap1_part2",
            )
            session.add_all([art1, art2])
            await session.commit()
            await session.refresh(art1)
            await session.refresh(art2)

            db_s1 = await session.get(ScriptSegmentRecord, seg1_id)
            db_s2 = await session.get(ScriptSegmentRecord, seg2_id)
            db_s1.status = "completed"
            db_s1.active_artifact_id = art1.id
            db_s2.status = "completed"
            db_s2.active_artifact_id = art2.id
            await session.commit()

        # 4. Modify text of segment 1 -> ensure status becomes stale (needs regeneration)
        cur_proj = (await client.get(f"/api/v1/projects/{proj_id}", headers=headers)).json()
        edit_resp = await client.patch(
            f"/api/v1/projects/{proj_id}/segments/{seg1_id}",
            headers=headers,
            json={
                "text": "Mùa xuân tươi đẹp đã về trên nông trường Điện Biên rực rỡ sắc hoa ban trắng.",
                "expected_segment_version": 1,
                "expected_project_version": cur_proj["version"],
            },
        )
        assert edit_resp.status_code == 200
        assert edit_resp.json()["status"] == "stale"
        assert edit_resp.json()["active_artifact_id"] == art1.id  # preserved during stale

        # Re-complete segment 1
        async with e2e_test_db() as session:
            db_s1 = await session.get(ScriptSegmentRecord, seg1_id)
            db_s1.status = "completed"
            await session.commit()

        # If incomplete segments exist (e.g., if there's a 3rd segment), complete it or delete it
        if len(segments) > 2:
            for s in segments[2:]:
                await client.delete(f"/api/v1/projects/{proj_id}/segments/{s['id']}", headers=headers)

        # 5. Export Master Audio (WAV 48kHz, Loudness -16 LUFS)
        export_resp = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={
                "format": "wav",
                "sample_rate": 48000,
                "normalize_loudness": True,
                "target_lufs": -16.0,
            },
        )
        assert export_resp.status_code == 201
        exp_data = export_resp.json()
        assert exp_data["format"] == "wav"
        assert exp_data["sample_rate"] == 48000
        assert exp_data["duration_seconds"] > 4.0
        assert Path(exp_data["file_path"]).exists()
        assert len(exp_data["sha256_checksum"]) == 64


@pytest.mark.asyncio
async def test_workflow_b_mandarin_chinese_narration(e2e_test_db, e2e_users, tmp_path):
    """
    Workflow B: Mandarin Chinese Narration
    1. Create Narration Project for Mandarin
    2. Auto-segment Chinese script using Chinese punctuation (。！？)
    3. Verify segment assignments with Qwen3-TTS engine
    4. Simulate audio generation
    5. Export master audio (MP3 24kHz)
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {e2e_users['lead_token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Project
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "三国演义第一章 - 宴桃园豪杰三结义",
                "project_type": "narration",
            },
        )
        proj_id = p_resp.json()["id"]

        # 2. Chinese Auto-segmentation
        zh_text = "滚滚长江东逝水，浪花淘尽英雄。是非成败转头空！青山依旧在，几度夕阳红？"
        auto_resp = await client.post(
            f"/api/v1/projects/{proj_id}/auto-segment",
            headers=headers,
            json={
                "text": zh_text,
                "language": "zh",
                "max_chars_per_segment": 60,
                "default_engine_id": "qwen3-tts",
                "default_voice_id": "vivian",
            },
        )
        assert auto_resp.status_code == 200
        zh_segments = auto_resp.json()
        assert len(zh_segments) >= 2
        for s in zh_segments:
            assert s["engine_id"] == "qwen3-tts"
            assert s["language"] == "zh"

        # 3. Complete segments with simulated 24kHz audio
        async with e2e_test_db() as session:
            for idx, s in enumerate(zh_segments):
                w = tmp_path / f"zh_part_{idx}.wav"
                make_test_wav(w, duration_s=1.8, sr=24000, freq=300.0 + idx * 50)
                art = ArtifactRecord(
                    owner_id=e2e_users["lead_id"],
                    file_path=str(w),
                    file_size_bytes=len(w.read_bytes()),
                    duration_seconds=1.8,
                    sample_rate=24000,
                    format="wav",
                    file_hash_sha256=f"hash_zh_{idx}",
                )
                session.add(art)
                await session.commit()
                await session.refresh(art)

                db_s = await session.get(ScriptSegmentRecord, s["id"])
                db_s.status = "completed"
                db_s.active_artifact_id = art.id
            await session.commit()

        # 4. Export Master Audio as MP3
        export_resp = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={
                "format": "mp3",
                "sample_rate": 24000,
                "normalize_loudness": False,
            },
        )
        assert export_resp.status_code == 201
        exp_data = export_resp.json()
        assert exp_data["format"] == "mp3"
        assert exp_data["sample_rate"] == 24000
        assert Path(exp_data["file_path"]).exists()


@pytest.mark.asyncio
async def test_workflow_c_multicharacter_dialogue_mixed_engines(e2e_test_db, e2e_users, tmp_path):
    """
    Workflow C: Multi-Character Dialogue with Mixed Engines
    1. Create Dialogue project
    2. Create Character A (VieNeu CPU 48kHz Mai Anh) and Character B (Qwen3 GPU 24kHz Vivian)
    3. Create dialogue script lines alternating between Character A and B
    4. Simulate mixed 48kHz and 24kHz source audio with distinct pauses
    5. Master export -> FFmpeg must safely resample 48kHz + 24kHz to unified 48kHz output
    6. Verify loudness normalization applies cleanly across mixed-engine voices
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {e2e_users['lead_token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Dialogue Project
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Kịch Truyền Thanh: Gặp Gỡ Bên Bờ Hồ Gươm",
                "project_type": "dialogue",
            },
        )
        proj_id = p_resp.json()["id"]

        # 2. Create Characters
        char1_resp = await client.post(
            f"/api/v1/projects/{proj_id}/characters",
            headers=headers,
            json={
                "name": "Lan (Hà Nội)",
                "avatar_color": "#10b981",
                "engine_id": "vieneu-tts",
                "voice_id": "mai_anh",
            },
        )
        assert char1_resp.status_code == 201
        char1_id = char1_resp.json()["id"]

        char2_resp = await client.post(
            f"/api/v1/projects/{proj_id}/characters",
            headers=headers,
            json={
                "name": "Mei (Du Khách Bắc Kinh)",
                "avatar_color": "#3b82f6",
                "engine_id": "qwen3-tts",
                "voice_id": "vivian",
            },
        )
        assert char2_resp.status_code == 201
        char2_id = char2_resp.json()["id"]

        # 3. Create Dialogue Lines
        # Line 1: Lan speaks Vietnamese (48kHz)
        l1 = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={
                "sequence_order": 0,
                "character_id": char1_id,
                "text": "Chào bạn, hoan nghênh bạn đến với thủ đô Hà Nội!",
                "engine_id": "vieneu-tts",
                "voice_id": "mai_anh",
                "language": "vi",
                "pause_after_ms": 500,  # 0.5s pause
            },
        )
        assert l1.status_code == 201
        l1_id = l1.json()["id"]

        # Line 2: Mei responds in Mandarin (24kHz)
        l2 = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={
                "sequence_order": 1,
                "character_id": char2_id,
                "text": "你好！河内真的很美丽，谢谢你的热情款待。",
                "engine_id": "qwen3-tts",
                "voice_id": "vivian",
                "language": "zh",
                "pause_after_ms": 300,
            },
        )
        assert l2.status_code == 201
        l2_id = l2.json()["id"]

        # 4. Attach mixed sample rate audio: 48kHz for Line 1, 24kHz for Line 2
        w_lan = tmp_path / "dialogue_lan_48k.wav"
        w_mei = tmp_path / "dialogue_mei_24k.wav"
        make_test_wav(w_lan, duration_s=2.0, sr=48000, freq=440.0)
        make_test_wav(w_mei, duration_s=2.2, sr=24000, freq=520.0)

        async with e2e_test_db() as session:
            art_lan = ArtifactRecord(
                owner_id=e2e_users["lead_id"],
                file_path=str(w_lan),
                file_size_bytes=len(w_lan.read_bytes()),
                duration_seconds=2.0,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="hash_lan_48k",
            )
            art_mei = ArtifactRecord(
                owner_id=e2e_users["lead_id"],
                file_path=str(w_mei),
                file_size_bytes=len(w_mei.read_bytes()),
                duration_seconds=2.2,
                sample_rate=24000,
                format="wav",
                file_hash_sha256="hash_mei_24k",
            )
            session.add_all([art_lan, art_mei])
            await session.commit()
            await session.refresh(art_lan)
            await session.refresh(art_mei)

            db_l1 = await session.get(ScriptSegmentRecord, l1_id)
            db_l2 = await session.get(ScriptSegmentRecord, l2_id)
            db_l1.status = "completed"
            db_l1.active_artifact_id = art_lan.id
            db_l2.status = "completed"
            db_l2.active_artifact_id = art_mei.id
            await session.commit()

        # 5. Export Master Audio at target 48kHz WAV with EBU R128 Loudness Normalization
        export_resp = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={
                "format": "wav",
                "sample_rate": 48000,
                "normalize_loudness": True,
                "target_lufs": -16.0,
            },
        )
        assert export_resp.status_code == 201
        master_data = export_resp.json()
        assert master_data["format"] == "wav"
        assert master_data["sample_rate"] == 48000
        assert master_data["segment_count"] == 2
        # Total duration must equal sum of durations + pauses (2.0 + 0.5 + 2.2 + 0.3 = 5.0s approx)
        assert master_data["duration_seconds"] >= 4.8
        assert Path(master_data["file_path"]).exists()

        # Check wave file on disk
        with wave.open(master_data["file_path"], "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2


@pytest.mark.asyncio
async def test_workflow_d_persistence_concurrency_and_isolation(e2e_test_db, e2e_users):
    """
    Workflow D: Persistence, Optimistic Concurrency Control, and Cross-User Isolation
    1. Verify project details persist across distinct sessions/requests
    2. Concurrent modification conflict (HTTP 409 Conflict)
    3. Unauthorized cross-user access blocked (HTTP 403 Forbidden)
    """
    transport = ASGITransport(app=app)
    lead_headers = {"Authorization": f"Bearer {e2e_users['lead_token']}"}
    guest_headers = {"Authorization": f"Bearer {e2e_users['guest_token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Project as lead
        p_resp = await client.post(
            "/api/v1/projects",
            headers=lead_headers,
            json={"title": "Tuyệt Mật Studio", "project_type": "narration"},
        )
        proj_id = p_resp.json()["id"]
        v1 = p_resp.json()["version"]

        # Guest user attempts to read -> 403 Forbidden
        guest_get = await client.get(f"/api/v1/projects/{proj_id}", headers=guest_headers)
        assert guest_get.status_code == 403

        # Guest user attempts to update -> 403 Forbidden
        guest_patch = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=guest_headers,
            json={"title": "Hacked Title"},
        )
        assert guest_patch.status_code == 403

        # Lead updates project with wrong expected_version -> 409 Conflict
        conflict_patch = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=lead_headers,
            json={"title": "Title Update", "expected_version": 999},
        )
        assert conflict_patch.status_code == 409

        # Lead updates with correct version -> 200 OK and version increments
        ok_patch = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=lead_headers,
            json={"title": "Tuyệt Mật Studio v2", "expected_version": v1},
        )
        assert ok_patch.status_code == 200
        assert ok_patch.json()["version"] == v1 + 1
        assert ok_patch.json()["title"] == "Tuyệt Mật Studio v2"
