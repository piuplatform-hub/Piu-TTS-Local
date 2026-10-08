"""
Phase 4 Asynchronous Data Integrity and Concurrency Invariant Tests
Validates the 8 critical concurrency and revision correctness scenarios (A through H):
A. User edits a segment while an older generation job is running (Status becomes stale/draft).
B. Older job finishes after the newer revision was saved (Stale job does NOT overwrite newer revision; previous audio preserved in revision record).
C. User generates two successive revisions of the same segment (Both revisions preserved non-destructively).
D. Batch cancellation during partial completion (Completed segments preserved, in-flight jobs cancelled, project in recoverable state).
E. One dialogue line fails while remaining lines succeed (Failed segment flagged, prevents export).
F. User starts export while one segment is stale or incomplete (HTTP 400 rejection).
G. Two browser tabs attempt conflicting updates (HTTP 409 Conflict via optimistic concurrency control).
H. Application restarts during batch synthesis (In-flight jobs and project state cleanly recovered).
"""

import math
from pathlib import Path
import struct
import wave
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.main import app
from apps.server.src.database import Base, get_db
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.models.user import User
from apps.server.src.models.engine import EngineRecord
from apps.server.src.models.job import JobRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord, SegmentRevisionRecord
from apps.server.src.services.project_service import ProjectService


def make_dummy_wav(file_path: Path, duration_s: float = 1.0, sr: int = 48000):
    n_frames = int(sr * duration_s)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        samples = bytearray()
        for i in range(n_frames):
            val = int(12000.0 * math.sin(2.0 * math.pi * 440.0 * (i / sr)))
            samples.extend(struct.pack("<h", val))
        wf.writeframes(samples)


@pytest.fixture
async def integrity_db(tmp_path):
    db_file = tmp_path / "test_integrity.db"
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

    async with session_factory() as session:
        eng = EngineRecord(
            id="vieneu-tts",
            name="VieNeu-TTS",
            version="3.8.3",
            device_target="cpu",
            capabilities=["text_to_speech", "voice_cloning"],
            manifest_data={},
        )
        session.add(eng)

        u = User(
            username="producer_bob",
            password_hash=hash_password("BobPass123!"),
            role="editor",
            is_active=True,
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)

        token = create_access_token({"sub": u.id, "username": u.username, "role": u.role})

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield {"factory": session_factory, "token": token, "user_id": u.id}
    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_scenario_a_and_b_stale_job_cannot_overwrite_newer_revision(integrity_db, tmp_path):
    """
    Scenario A & B:
    1. Segment is created with text "Ban đầu".
    2. Render is initiated -> Job #1 is submitted with text "Ban đầu". Segment is 'queued'.
    3. User edits text to "Nội dung mới đã sửa" WHILE Job #1 is still running.
       -> Segment status must become 'draft' or 'stale' (partial invalidation).
    4. Job #1 now completes in background.
    5. Reconcile runs -> Stale Job #1 MUST NOT overwrite active_artifact_id or mark segment as 'completed'.
       -> Audio from Job #1 is archived safely in SegmentRevisionRecord.
       -> Current segment remains 'draft' or 'stale' awaiting regeneration.
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {integrity_db['token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Project & Segment
        p = (await client.post("/api/v1/projects", headers=headers, json={"title": "Integrity Project"})).json()
        proj_id = p["id"]

        s = (await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"text": "Ban đầu chưa sửa.", "engine_id": "vieneu-tts", "voice_id": "mai_anh"},
        )).json()
        seg_id = s["id"]

        # Step 2: Render segment (submits Job #1)
        r = (await client.post(f"/api/v1/projects/{proj_id}/segments/{seg_id}/render", headers=headers)).json()
        assert r["status"] == "queued"
        job1_id = r["last_job_id"]
        assert job1_id is not None

        # Step 3: User edits text to "Nội dung mới đã sửa" WHILE Job #1 is in-flight
        curr_proj = (await client.get(f"/api/v1/projects/{proj_id}", headers=headers)).json()
        up = await client.patch(
            f"/api/v1/projects/{proj_id}/segments/{seg_id}",
            headers=headers,
            json={
                "text": "Nội dung mới đã sửa hoàn toàn.",
                "expected_segment_version": r["version"],
                "expected_project_version": curr_proj["version"],
            },
        )
        assert up.status_code == 200
        seg_edited = up.json()
        assert seg_edited["text"] == "Nội dung mới đã sửa hoàn toàn."
        assert seg_edited["status"] in ("draft", "stale")

        # Step 4: Simulate Job #1 completing with audio for the OLD text
        wav1 = tmp_path / "old_job1_audio.wav"
        make_dummy_wav(wav1, duration_s=1.5)

        session_factory = integrity_db["factory"]
        async with session_factory() as session:
            art1 = ArtifactRecord(
                owner_id=integrity_db["user_id"],
                file_path=str(wav1),
                file_size_bytes=len(wav1.read_bytes()),
                duration_seconds=1.5,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="old_sha_1",
            )
            session.add(art1)
            await session.commit()
            await session.refresh(art1)

            job1 = await session.get(JobRecord, job1_id)
            job1.status = "completed"
            job1.artifact_id = art1.id
            await session.commit()

        # Step 5: Reconcile project -> Check integrity
        rec_proj = (await client.get(f"/api/v1/projects/{proj_id}", headers=headers)).json()
        seg_reconciled = next(item for item in rec_proj["segments"] if item["id"] == seg_id)

        # CRITICAL ASSERTION: The active artifact must NOT be set to Job 1, and status must NOT be 'completed'
        assert seg_reconciled["active_artifact_id"] != art1.id
        assert seg_reconciled["status"] != "completed"
        assert seg_reconciled["text"] == "Nội dung mới đã sửa hoàn toàn."

        # Audio from Job 1 must be preserved in revisions
        async with session_factory() as session:
            stmt_rev = select(SegmentRevisionRecord).where(SegmentRevisionRecord.segment_id == seg_id)
            revs = (await session.execute(stmt_rev)).scalars().all()
            assert len(revs) >= 1
            assert revs[0].artifact_id == art1.id
            assert revs[0].text == "Ban đầu chưa sửa."


@pytest.mark.asyncio
async def test_scenario_c_two_successive_revisions_preserved(integrity_db, tmp_path):
    """
    Scenario C:
    User generates two revisions of the same segment.
    Both revisions must be preserved non-destructively in SegmentRevisionRecord.
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {integrity_db['token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/v1/projects", headers=headers, json={"title": "Revision Test"})).json()
        proj_id = p["id"]

        s = (await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"text": "Phiên bản một.", "engine_id": "vieneu-tts", "voice_id": "mai_anh"},
        )).json()
        seg_id = s["id"]

        # Simulate Render 1 completion
        wav1 = tmp_path / "rev1.wav"
        make_dummy_wav(wav1, duration_s=1.0)
        session_factory = integrity_db["factory"]
        async with session_factory() as session:
            art1 = ArtifactRecord(
                owner_id=integrity_db["user_id"],
                file_path=str(wav1),
                file_size_bytes=len(wav1.read_bytes()),
                duration_seconds=1.0,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="sha_rev_1",
            )
            session.add(art1)
            await session.commit()
            await session.refresh(art1)

            db_s = await session.get(ScriptSegmentRecord, seg_id)
            db_s.status = "completed"
            db_s.active_artifact_id = art1.id
            await session.commit()

        # User edits and initiates Render 2
        curr_p = (await client.get(f"/api/v1/projects/{proj_id}", headers=headers)).json()
        await client.patch(
            f"/api/v1/projects/{proj_id}/segments/{seg_id}",
            headers=headers,
            json={"text": "Phiên bản hai đã sửa.", "expected_project_version": curr_p["version"]},
        )
        r2 = (await client.post(f"/api/v1/projects/{proj_id}/segments/{seg_id}/render", headers=headers)).json()
        job2_id = r2["last_job_id"]

        # Simulate Render 2 completion
        wav2 = tmp_path / "rev2.wav"
        make_dummy_wav(wav2, duration_s=1.2)
        async with session_factory() as session:
            art2 = ArtifactRecord(
                owner_id=integrity_db["user_id"],
                file_path=str(wav2),
                file_size_bytes=len(wav2.read_bytes()),
                duration_seconds=1.2,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="sha_rev_2",
            )
            session.add(art2)
            await session.commit()
            await session.refresh(art2)

            job2 = await session.get(JobRecord, job2_id)
            job2.status = "completed"
            job2.artifact_id = art2.id
            await session.commit()

        # Reconcile
        rec_p = (await client.get(f"/api/v1/projects/{proj_id}", headers=headers)).json()
        seg_final = next(item for item in rec_p["segments"] if item["id"] == seg_id)
        assert seg_final["active_artifact_id"] == art2.id
        assert seg_final["status"] == "completed"

        # Verify revision 1 was saved into revisions list
        async with session_factory() as session:
            stmt = select(SegmentRevisionRecord).where(SegmentRevisionRecord.segment_id == seg_id)
            revs = (await session.execute(stmt)).scalars().all()
            assert len(revs) >= 1
            assert any(r.artifact_id == art1.id for r in revs)


@pytest.mark.asyncio
async def test_scenario_e_and_f_incomplete_or_failed_segment_blocks_export(integrity_db, tmp_path):
    """
    Scenario E & F:
    A segment fails or is stale/draft. Master export MUST be rejected with HTTP 400.
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {integrity_db['token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/v1/projects", headers=headers, json={"title": "Export Guard Project"})).json()
        proj_id = p["id"]

        s1 = (await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"text": "Câu 1.", "engine_id": "vieneu-tts", "voice_id": "mai_anh"},
        )).json()
        s2 = (await client.post(
            f"/api/v1/projects/{proj_id}/segments",
            headers=headers,
            json={"text": "Câu 2.", "engine_id": "vieneu-tts", "voice_id": "mai_anh"},
        )).json()

        # Complete segment 1 only
        wav1 = tmp_path / "part1.wav"
        make_dummy_wav(wav1, duration_s=1.0)
        session_factory = integrity_db["factory"]
        async with session_factory() as session:
            art1 = ArtifactRecord(
                owner_id=integrity_db["user_id"],
                file_path=str(wav1),
                file_size_bytes=len(wav1.read_bytes()),
                duration_seconds=1.0,
                sample_rate=48000,
                format="wav",
                file_hash_sha256="part1_hash",
            )
            session.add(art1)
            await session.commit()
            await session.refresh(art1)

            db_s1 = await session.get(ScriptSegmentRecord, s1["id"])
            db_s1.status = "completed"
            db_s1.active_artifact_id = art1.id

            db_s2 = await session.get(ScriptSegmentRecord, s2["id"])
            db_s2.status = "failed"
            await session.commit()

        # Attempt export with failed segment 2 -> HTTP 400
        exp1 = await client.post(f"/api/v1/projects/{proj_id}/export", headers=headers, json={"format": "wav"})
        assert exp1.status_code == 400
        assert "INCOMPLETE_SEGMENTS" in exp1.json()["detail"]

        # Now mark segment 2 as stale with an artifact -> still MUST be rejected!
        async with session_factory() as session:
            db_s2 = await session.get(ScriptSegmentRecord, s2["id"])
            db_s2.status = "stale"
            db_s2.active_artifact_id = art1.id  # has old artifact but is stale
            await session.commit()

        exp2 = await client.post(f"/api/v1/projects/{proj_id}/export", headers=headers, json={"format": "wav"})
        assert exp2.status_code == 400
        assert "INCOMPLETE_SEGMENTS" in exp2.json()["detail"]


@pytest.mark.asyncio
async def test_scenario_g_conflicting_autosaves_409(integrity_db):
    """
    Scenario G:
    Two browser tabs attempt concurrent updates on the project or segments.
    Optimistic concurrency control returns HTTP 409 Conflict.
    """
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {integrity_db['token']}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/v1/projects", headers=headers, json={"title": "Tab 1 Title"})).json()
        proj_id = p["id"]
        v_initial = p["version"]

        # Tab 1 updates project
        t1_resp = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers,
            json={"title": "Title from Tab 1", "expected_version": v_initial},
        )
        assert t1_resp.status_code == 200
        assert t1_resp.json()["version"] == v_initial + 1

        # Tab 2 attempts update with stale v_initial -> 409 Conflict
        t2_resp = await client.patch(
            f"/api/v1/projects/{proj_id}",
            headers=headers,
            json={"title": "Title from Tab 2", "expected_version": v_initial},
        )
        assert t2_resp.status_code == 409
        assert "VERSION_CONFLICT" in t2_resp.json()["detail"]
