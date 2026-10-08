"""
Integration Tests for Phase 4 Project Workspace API
Verifies CRUD, optimistic concurrency control (409 Conflict), cross-user authorization (403 Forbidden),
character management, and script segment synchronization with partial stale invalidation.
"""

import json
import math
from pathlib import Path
import struct
import wave
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.main import app
from apps.server.src.database import Base, get_db
from apps.server.src.services.auth_service import AuthService
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.schemas.auth import UserCreateRequest
from apps.server.src.models.user import User
from apps.server.src.models.engine import EngineRecord


@pytest.fixture
async def setup_test_db(tmp_path):
    db_file = tmp_path / "test_projects.db"
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

    # Seed mock engine for FK constraints
    async with session_factory() as session:
        mock_eng = EngineRecord(
            id="vieneu-tts",
            name="VieNeu-TTS",
            version="3.8.3",
            device_target="cpu",
            capabilities=["text_to_speech", "voice_cloning"],
            manifest_data={},
        )
        session.add(mock_eng)
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.fixture
async def auth_tokens(setup_test_db):
    session_factory = setup_test_db
    async with session_factory() as session:
        # Create user A
        user_a = User(
            username="author_alice",
            password_hash=hash_password("Password123!"),
            role="editor",
            is_active=True,
        )
        session.add(user_a)

        # Create user B
        user_b = User(
            username="author_bob",
            password_hash=hash_password("Password123!"),
            role="editor",
            is_active=True,
        )
        session.add(user_b)
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)

        token_a = create_access_token({"sub": user_a.id, "username": user_a.username, "role": user_a.role})
        token_b = create_access_token({"sub": user_b.id, "username": user_b.username, "role": user_b.role})

    return {"alice": token_a, "bob": token_b, "alice_id": user_a.id, "bob_id": user_b.id}


@pytest.mark.asyncio
async def test_project_crud_and_persistence(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers_a = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        resp = await client.post(
            "/api/v1/projects",
            headers=headers_a,
            json={
                "title": "Hành Trình Về Phương Đông",
                "description": "Dự án chuyển thể sách nói audio",
                "project_type": "narration",
                "settings": {"target_sample_rate": 48000, "default_pause_ms": 400},
            },
        )
        assert resp.status_code == 201, resp.text
        proj = resp.json()
        assert proj["title"] == "Hành Trình Về Phương Đông"
        assert proj["version"] == 1
        proj_id = proj["id"]

        # 2. Get project details
        resp_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_a)
        assert resp_get.status_code == 200
        assert resp_get.json()["id"] == proj_id

        # 3. Update project
        resp_patch = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers_a,
            json={
                "title": "Hành Trình Về Phương Đông (Tập 1)",
                "settings": {"default_pause_ms": 500},
            },
        )
        assert resp_patch.status_code == 200
        updated = resp_patch.json()
        assert updated["title"] == "Hành Trình Về Phương Đông (Tập 1)"
        assert updated["version"] == 2
        assert updated["settings"]["default_pause_ms"] == 500

        # 4. List projects
        resp_list = await client.get("/api/v1/projects", headers=headers_a)
        assert resp_list.status_code == 200
        summaries = resp_list.json()
        assert len(summaries) >= 1
        assert summaries[0]["id"] == proj_id

        # 5. Delete project
        resp_del = await client.delete(f"/api/v1/projects/{proj_id}", headers=headers_a)
        assert resp_del.status_code == 204

        # Verify 404 after deletion
        resp_get_after = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_a)
        assert resp_get_after.status_code == 404


@pytest.mark.asyncio
async def test_project_optimistic_concurrency_conflict(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project (starts at version 1)
        resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Concurrent Story", "project_type": "narration"},
        )
        proj_id = resp.json()["id"]
        assert resp.json()["version"] == 1

        # Tab 1 updates project with expected_version=1 -> succeeds, version becomes 2
        resp1 = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers,
            json={"title": "Story by Tab 1", "expected_version": 1},
        )
        assert resp1.status_code == 200
        assert resp1.json()["version"] == 2

        # Tab 2 tries to update with stale expected_version=1 -> rejected with 409 Conflict
        resp2 = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers,
            json={"title": "Story by Tab 2 (Stale)", "expected_version": 1},
        )
        assert resp2.status_code == 409
        assert "VERSION_CONFLICT" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_cross_user_project_isolation(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers_alice = {"Authorization": f"Bearer {auth_tokens['alice']}"}
    headers_bob = {"Authorization": f"Bearer {auth_tokens['bob']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Alice creates private project
        resp = await client.post(
            "/api/v1/projects",
            headers=headers_alice,
            json={"title": "Alice Confidential", "project_type": "narration"},
        )
        proj_id = resp.json()["id"]

        # Bob tries to access Alice's project -> 403 Forbidden
        resp_bob_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_bob)
        assert resp_bob_get.status_code == 403
        assert "FORBIDDEN_PROJECT_ACCESS" in resp_bob_get.json()["detail"]

        # Bob tries to update Alice's project -> 403 Forbidden
        resp_bob_patch = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers_bob,
            json={"title": "Hacked by Bob"},
        )
        assert resp_bob_patch.status_code == 403

        # Bob tries to delete Alice's project -> 403 Forbidden
        resp_bob_del = await client.delete(f"/api/v1/projects/{proj_id}", headers=headers_bob)
        assert resp_bob_del.status_code == 403


@pytest.mark.asyncio
async def test_character_crud_and_voice_persona(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create dialogue project
        resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Radio Play Dialogue", "project_type": "dialogue"},
        )
        proj_id = resp.json()["id"]

        # 1. Create character
        resp_char = await client.post(
            f"/api/v1/projects/{proj_id}/characters",
            headers=headers,
            json={
                "name": "Người Dẫn Chuyện",
                "avatar_color": "#3b82f6",
                "engine_id": "vieneu-tts",
                "voice_id": "hai_dang",
                "language": "vi",
                "parameters": {"speed": 1.0},
            },
        )
        assert resp_char.status_code == 201
        char = resp_char.json()
        assert char["name"] == "Người Dẫn Chuyện"
        char_id = char["id"]

        # 2. Update character
        resp_char_up = await client.patch(
            f"/api/v1/projects/{proj_id}/characters/{char_id}",
            headers=headers,
            json={"name": "MC Hải Đăng", "avatar_color": "#10b981"},
        )
        assert resp_char_up.status_code == 200
        assert resp_char_up.json()["name"] == "MC Hải Đăng"
        assert resp_char_up.json()["avatar_color"] == "#10b981"

        # 3. Delete character
        resp_char_del = await client.delete(f"/api/v1/projects/{proj_id}/characters/{char_id}", headers=headers)
        assert resp_char_del.status_code == 204


@pytest.mark.asyncio
async def test_segment_crud_and_partial_stale_invalidation(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_p = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Narration Episode", "project_type": "narration"},
        )
        proj_id = resp_p.json()["id"]

        # 1. Add segment
        resp_s = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={
                "sequence_order": 0,
                "text": "Đoạn văn đầu tiên của câu chuyện.",
                "language": "vi",
                "engine_id": "vieneu-tts",
                "voice_id": "hai_dang",
                "pause_after_ms": 350,
            },
        )
        assert resp_s.status_code == 201
        seg = resp_s.json()
        assert seg["status"] == "draft"
        seg_id = seg["id"]

        # 2. Simulate completed state directly in DB
        session_factory = setup_test_db
        from apps.server.src.models.segment import ScriptSegmentRecord
        async with session_factory() as session:
            db_seg = await session.get(ScriptSegmentRecord, seg_id)
            db_seg.status = "completed"
            await session.commit()

        # Verify it is completed
        resp_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers)
        assert resp_get.json()["segments"][0]["status"] == "completed"

        # 3. Edit segment text -> should automatically transition to 'stale' (Needs Regeneration)
        resp_up = await client.patch(
            f"/api/v1/projects/{proj_id}/segments/{seg_id}",
            headers=headers,
            json={"text": "Đoạn văn đầu tiên đã được tác giả chỉnh sửa lại."},
        )
        assert resp_up.status_code == 200
        updated_seg = resp_up.json()
        assert updated_seg["status"] == "stale", "Editing completed segment must mark it as stale"
        assert updated_seg["text"] == "Đoạn văn đầu tiên đã được tác giả chỉnh sửa lại."


@pytest.mark.asyncio
async def test_bulk_sync_segments_and_autosave(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_p = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Bulk Sync Document", "project_type": "narration"},
        )
        proj = resp_p.json()
        proj_id = proj["id"]
        v1 = proj["version"]

        # Bulk sync 3 segments
        bulk_payload = {
            "expected_project_version": v1,
            "segments": [
                {
                    "sequence_order": 0,
                    "text": "Câu mở đầu.",
                    "language": "vi",
                    "engine_id": "vieneu-tts",
                    "voice_id": "hai_dang",
                },
                {
                    "sequence_order": 1,
                    "text": "Câu thân bài.",
                    "language": "vi",
                    "engine_id": "vieneu-tts",
                    "voice_id": "mai_anh",
                },
                {
                    "sequence_order": 2,
                    "text": "Câu kết luận.",
                    "language": "vi",
                    "engine_id": "vieneu-tts",
                    "voice_id": "hai_dang",
                },
            ]
        }

        resp_sync = await client.put(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json=bulk_payload,
        )
        assert resp_sync.status_code == 200
        synced_segs = resp_sync.json()
        assert len(synced_segs) == 3
        assert synced_segs[0]["sequence_order"] == 0
        assert synced_segs[1]["sequence_order"] == 1
        assert synced_segs[2]["sequence_order"] == 2

        # Check project version increased
        resp_p2 = await client.get(f"/api/v1/projects/{proj_id}", headers=headers)
        assert resp_p2.json()["version"] > v1


def make_dummy_wav(path: Path, duration_s: float = 1.0, sr: int = 48000):
    n_samples = int(duration_s * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n_samples):
            val = int(32767.0 * 0.2 * math.sin(2 * math.pi * 440.0 * i / sr))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


@pytest.mark.asyncio
async def test_auto_segmentation_endpoint(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Preview segmentation endpoint
        preview_resp = await client.post(
            "/api/v1/projects/segment-text",
            headers=headers,
            json={
                "text": "Câu thứ nhất rất hay. Câu thứ hai tiếp nối câu chuyện. Câu thứ ba kết thúc chương.",
                "language": "vi",
                "max_chars_per_segment": 100,
            },
        )
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        assert preview_data["segment_count"] >= 3

        # 2. Project auto-segment endpoint
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Auto Segmented Book", "project_type": "narration"},
        )
        proj_id = p_resp.json()["id"]

        auto_resp = await client.post(
            f"/api/v1/projects/{proj_id}/auto-segment",
            headers=headers,
            json={
                "text": "Đoạn một của sách. Đoạn hai của sách. Đoạn ba của sách.",
                "language": "vi",
                "max_chars_per_segment": 100,
            },
        )
        assert auto_resp.status_code == 200
        segments = auto_resp.json()
        assert len(segments) >= 3
        assert segments[0]["status"] == "draft"


@pytest.mark.asyncio
async def test_render_single_and_batch_segments(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project with 2 segments
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Rendering Project", "project_type": "narration"},
        )
        proj_id = p_resp.json()["id"]

        # Add segment 1
        s1_resp = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={
                "sequence_order": 0,
                "text": "Câu số 1.",
                "language": "vi",
                "engine_id": "vieneu-tts",
                "voice_id": "hai_dang",
            },
        )
        seg1_id = s1_resp.json()["id"]

        # Render single segment
        render1 = await client.post(
            f"/api/v1/projects/{proj_id}/segments/{seg1_id}/render",
            headers=headers,
        )
        assert render1.status_code == 200
        assert render1.json()["status"] == "queued"
        assert render1.json()["last_job_id"] is not None

        # Add segment 2
        s2_resp = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={
                "sequence_order": 1,
                "text": "Câu số 2.",
                "language": "vi",
                "engine_id": "vieneu-tts",
                "voice_id": "mai_anh",
            },
        )
        seg2_id = s2_resp.json()["id"]

        # Batch render (should pick up remaining draft segment)
        batch_resp = await client.post(
            f"/api/v1/projects/{proj_id}/render-batch",
            headers=headers,
        )
        assert batch_resp.status_code == 200
        batch_results = batch_resp.json()
        assert len(batch_results) >= 1
        assert any(s["id"] == seg2_id and s["status"] == "queued" for s in batch_results)


@pytest.mark.asyncio
async def test_master_audio_export_wav_and_mp3(setup_test_db, auth_tokens, tmp_path):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Master Export Book", "project_type": "narration"},
        )
        proj_id = p_resp.json()["id"]

        # Add 2 segments
        s1 = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"sequence_order": 0, "text": "Câu đầu tiên.", "engine_id": "vieneu-tts", "voice_id": "hai_dang", "pause_after_ms": 200},
        )
        s2 = await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"sequence_order": 1, "text": "Câu thứ hai.", "engine_id": "vieneu-tts", "voice_id": "mai_anh", "pause_after_ms": 200},
        )
        seg1_id = s1.json()["id"]
        seg2_id = s2.json()["id"]

        # Create dummy WAV files for artifacts
        wav1 = tmp_path / "audio_part1.wav"
        wav2 = tmp_path / "audio_part2.wav"
        make_dummy_wav(wav1, duration_s=1.5, sr=48000)
        make_dummy_wav(wav2, duration_s=1.2, sr=24000)  # Mixed sample rate to test resampler!

        # Attach artifacts and complete segments in DB
        session_factory = setup_test_db
        from apps.server.src.models.artifact import ArtifactRecord
        from apps.server.src.models.segment import ScriptSegmentRecord

        async with session_factory() as session:
            art1 = ArtifactRecord(
                owner_id=auth_tokens["alice_id"],
                file_path=str(wav1),
                file_size_bytes=len(wav1.read_bytes()),
                duration_seconds=1.5,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="dummy_sha_1",
            )
            art2 = ArtifactRecord(
                owner_id=auth_tokens["alice_id"],
                file_path=str(wav2),
                file_size_bytes=len(wav2.read_bytes()),
                duration_seconds=1.2,
                sample_rate=24000,
                format="wav",
                file_hash_sha256="dummy_sha_2",
            )
            session.add_all([art1, art2])
            await session.commit()
            await session.refresh(art1)
            await session.refresh(art2)

            db_s1 = await session.get(ScriptSegmentRecord, seg1_id)
            db_s2 = await session.get(ScriptSegmentRecord, seg2_id)
            db_s1.active_artifact_id = art1.id
            db_s1.status = "completed"
            db_s2.active_artifact_id = art2.id
            db_s2.status = "completed"
            await session.commit()

        # 1. Export as Master WAV (normalized to 48kHz with EBU R128)
        exp_wav = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={"format": "wav", "sample_rate": 48000, "normalize_loudness": True, "target_lufs": -16.0},
        )
        assert exp_wav.status_code == 201, exp_wav.text
        wav_data = exp_wav.json()
        assert wav_data["format"] == "wav"
        assert wav_data["sample_rate"] == 48000
        assert wav_data["segment_count"] == 2
        assert Path(wav_data["file_path"]).is_file()
        assert wav_data["duration_seconds"] > 2.0  # 1.5s + 0.2s pause + 1.2s + 0.2s pause

        # Test download with Authorization header
        dl_wav = await client.get(
            f"/api/v1/projects/{proj_id}/exports/{wav_data['id']}/download",
            headers=headers,
        )
        assert dl_wav.status_code == 200
        assert dl_wav.headers["content-type"] == "audio/wav"
        assert 'attachment; filename="' in dl_wav.headers.get("content-disposition", "")
        assert len(dl_wav.content) > 1000

        # Test browser download via query parameter '?token=' (direct route)
        dl_token_direct = await client.get(
            f"/api/v1/projects/exports/{wav_data['id']}/download?token={auth_tokens['alice']}",
        )
        assert dl_token_direct.status_code == 200
        assert dl_token_direct.headers["content-type"] == "audio/wav"
        assert 'attachment; filename="' in dl_token_direct.headers.get("content-disposition", "")
        assert len(dl_token_direct.content) == len(dl_wav.content)

        # Test browser download via query parameter '?token=' (nested project route)
        dl_token_nested = await client.get(
            f"/api/v1/projects/{proj_id}/exports/{wav_data['id']}/download?token={auth_tokens['alice']}",
        )
        assert dl_token_nested.status_code == 200
        assert len(dl_token_nested.content) == len(dl_wav.content)

        # Security check: Unauthenticated download without token or header -> 401
        dl_unauth = await client.get(
            f"/api/v1/projects/exports/{wav_data['id']}/download",
        )
        assert dl_unauth.status_code == 401

        # Security check: Cross-user download by Bob on Alice's export -> 403 Forbidden
        dl_cross_query = await client.get(
            f"/api/v1/projects/exports/{wav_data['id']}/download?token={auth_tokens['bob']}",
        )
        assert dl_cross_query.status_code == 403

        dl_cross_header = await client.get(
            f"/api/v1/projects/{proj_id}/exports/{wav_data['id']}/download",
            headers={"Authorization": f"Bearer {auth_tokens['bob']}"},
        )
        assert dl_cross_header.status_code == 403

        # 2. Export as Master MP3 (320kbps)
        exp_mp3 = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={"format": "mp3", "sample_rate": 48000, "normalize_loudness": False},
        )
        assert exp_mp3.status_code == 201, exp_mp3.text
        mp3_data = exp_mp3.json()
        assert mp3_data["format"] == "mp3"
        assert Path(mp3_data["file_path"]).is_file()

        # Test download MP3 via browser token query param
        dl_mp3 = await client.get(
            f"/api/v1/projects/exports/{mp3_data['id']}/download?token={auth_tokens['alice']}",
        )
        assert dl_mp3.status_code == 200
        assert dl_mp3.headers["content-type"] == "audio/mpeg"
        assert 'attachment; filename="' in dl_mp3.headers.get("content-disposition", "")
        assert len(dl_mp3.content) > 1000


@pytest.mark.asyncio
async def test_master_export_rejects_incomplete_project(setup_test_db, auth_tokens):
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {auth_tokens['alice']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_resp = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Incomplete Book", "project_type": "narration"},
        )
        proj_id = p_resp.json()["id"]

        # Add segment in draft status
        await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"sequence_order": 0, "text": "Câu chưa render.", "engine_id": "vieneu-tts", "voice_id": "hai_dang"},
        )

        # Attempt to export -> must be rejected with 400 Bad Request
        exp_resp = await client.post(
            f"/api/v1/projects/{proj_id}/export",
            headers=headers,
            json={"format": "wav"},
        )
        assert exp_resp.status_code == 400
        assert "INCOMPLETE_SEGMENTS" in exp_resp.json()["detail"]
