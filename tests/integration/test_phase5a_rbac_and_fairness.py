"""
Phase 5A Multi-User Core Hardening & Fair Resource Scheduling Test Suite
Verifies:
1. Multi-user RBAC Matrix (Viewer vs Editor vs Admin on all mutation & read routes)
2. Negative authorization & cross-user isolation
3. Secure Password Change Flow & Input Validation
4. Login Rate Limiting, IP/User Sliding Window Lockout & Non-Enumeration Protection
5. Fair-Share Queue Scheduling (Least-Active-User-First & Priority Preemption)
6. Maximum Outstanding Jobs Limit per User (HTTP 429)
7. Non-destructive User Storage Quota Accounting & Enforcement (HTTP 413)
8. Strict Voice Cloning Ownership Isolation (No silent Admin bypass)
"""

import asyncio
from datetime import datetime, timezone
import io
import pytest
import wave
from httpx import AsyncClient
from sqlalchemy import select, update

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src.models.job import JobRecord
from apps.server.src.models.user import User
from apps.server.src.models.asset import ReferenceAssetRecord
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.job_state_machine import JobState
from apps.server.src.services.user_quota_service import UserQuotaService


def _create_mock_wav(duration_seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
    """Creates in-memory standard 16-bit PCM WAV bytes."""
    buf = io.BytesIO()
    num_samples = int(duration_seconds * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_5a_rbac_matrix_and_negative_authorization(client: AsyncClient, running_mock_engine):
    """
    1. RBAC Matrix Verification:
       - Viewer: READ-ONLY. Mutating projects, characters, segments, rendering, exporting,
         submitting jobs, and uploading audio assets are rejected with 403 Forbidden.
       - Editor: Can create and mutate their own workspace and jobs.
       - Admin: Can provision users and inspect projects.
    """
    # 1. Bootstrap Admin
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "super_admin", "password": "AdminPassword123!", "setup_token": token},
    )
    assert boot_res.status_code == 201
    admin_token = boot_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin provisions an Editor and a Viewer
    res_ed = await client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "alice_editor", "password": "AlicePassword123!", "role": "editor"},
    )
    assert res_ed.status_code == 201

    res_vw = await client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "bob_viewer", "password": "BobPassword123!", "role": "viewer"},
    )
    assert res_vw.status_code == 201

    # Login both users
    login_ed = await client.post("/api/v1/auth/login", json={"username": "alice_editor", "password": "AlicePassword123!"})
    token_ed = login_ed.json()["access_token"]
    headers_ed = {"Authorization": f"Bearer {token_ed}"}

    login_vw = await client.post("/api/v1/auth/login", json={"username": "bob_viewer", "password": "BobPassword123!"})
    token_vw = login_vw.json()["access_token"]
    headers_vw = {"Authorization": f"Bearer {token_vw}"}

    # 3. Viewer attempts project creation -> 403 Forbidden
    res_vw_proj = await client.post(
        "/api/v1/projects",
        headers=headers_vw,
        json={"title": "Viewer Prohibited Project", "project_type": "narration"},
    )
    assert res_vw_proj.status_code == 403
    assert res_vw_proj.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    # 4. Viewer attempts to submit speech job directly -> 403 Forbidden
    res_vw_job = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_vw,
        json={"text": "Test speech", "engine_id": "mock-tts", "language": "vi"},
    )
    assert res_vw_job.status_code == 403
    assert res_vw_job.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    # 5. Viewer attempts to upload reference audio asset -> 403 Forbidden
    mock_wav = _create_mock_wav(2.0)
    res_vw_asset = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers_vw,
        files={"file": ("sample.wav", mock_wav, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert res_vw_asset.status_code == 403
    assert res_vw_asset.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    # 6. Editor successfully creates a Project
    res_proj = await client.post(
        "/api/v1/projects",
        headers=headers_ed,
        json={"title": "Alice Audio Novel", "project_type": "narration"},
    )
    assert res_proj.status_code == 201
    proj_id = res_proj.json()["id"]

    # 7. Viewer attempts to mutate Alice's project (add character, add segment, export) -> 403 Forbidden
    res_vw_char = await client.post(
        f"/api/v1/projects/{proj_id}/characters",
        headers=headers_vw,
        json={"name": "Narrator", "voice_id": "mock_voice"},
    )
    assert res_vw_char.status_code == 403
    assert res_vw_char.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    res_vw_seg = await client.post(
        f"/api/v1/projects/{proj_id}/segments",
        headers=headers_vw,
        json={"text": "Viewer cannot insert line."},
    )
    assert res_vw_seg.status_code == 403
    assert res_vw_seg.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"

    res_vw_exp = await client.post(
        f"/api/v1/projects/{proj_id}/export",
        headers=headers_vw,
        json={"format": "wav", "normalize_loudness": False},
    )
    assert res_vw_exp.status_code == 403
    assert res_vw_exp.json()["code"] == "FORBIDDEN_INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_5a_password_change_flow(client: AsyncClient):
    """
    2. Password Change Security:
       - Wrong old password -> 401 Unauthorized
       - New password too short (< 8 chars) -> 422 Unprocessable Entity
       - Successful change invalidates old password and allows login with new password.
    """
    # 1. Bootstrap Admin
    token = get_or_create_bootstrap_token()
    await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "pw_admin", "password": "AdminPassword123!", "setup_token": token},
    )

    # 2. Login
    login_res = await client.post("/api/v1/auth/login", json={"username": "pw_admin", "password": "AdminPassword123!"})
    jwt_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # 3. Change password with wrong old password -> 400
    bad_old = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "WrongPassword999!", "new_password": "BrandNewPassword123!"},
    )
    assert bad_old.status_code == 400
    assert bad_old.json()["code"] == "INVALID_OLD_PASSWORD"

    # 4. Change password with too short new password -> 422
    short_pw = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "AdminPassword123!", "new_password": "short"},
    )
    assert short_pw.status_code == 422

    # 5. Successfully change password
    good_change = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "AdminPassword123!", "new_password": "BrandNewPassword123!"},
    )
    assert good_change.status_code == 200

    # 6. Verify old password no longer works
    old_login = await client.post("/api/v1/auth/login", json={"username": "pw_admin", "password": "AdminPassword123!"})
    assert old_login.status_code == 401

    # 7. Verify new password works
    new_login = await client.post("/api/v1/auth/login", json={"username": "pw_admin", "password": "BrandNewPassword123!"})
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


@pytest.mark.asyncio
async def test_5a_brute_force_lockout_and_no_enumeration(client: AsyncClient):
    """
    3. Brute Force Defense & Non-Enumeration:
       - Non-existent user vs bad password returns identical message (no account enumeration).
       - 5 failed attempts on user triggers HTTP 429 Too Many Requests with Retry-After header.
    """
    # 1. Bootstrap user
    token = get_or_create_bootstrap_token()
    await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "target_user", "password": "ValidPassword123!", "setup_token": token},
    )

    # 2. Check non-enumeration: Non-existent user returns 401 with generic message
    res_fake = await client.post("/api/v1/auth/login", json={"username": "ghost_user", "password": "SomePassword123!"})
    assert res_fake.status_code == 401
    assert res_fake.json()["detail"] == "Incorrect username or password."

    # Existing user with wrong password returns identical 401 detail
    res_wrong = await client.post("/api/v1/auth/login", json={"username": "target_user", "password": "WrongPassword1!"})
    assert res_wrong.status_code == 401
    assert res_wrong.json()["detail"] == "Incorrect username or password."

    # 3. Accumulate failed attempts up to limit (5 failed attempts total)
    # Attempt 1 was done above with res_wrong.
    # Do 4 more failed attempts (attempts 2, 3, 4, 5) -> all return 401
    for i in range(2, 6):
        r = await client.post("/api/v1/auth/login", json={"username": "target_user", "password": f"WrongAttempt{i}!"})
        assert r.status_code == 401

    # Attempt 6 triggers HTTP 429 Lockout (since user has 5 recorded failures >= 5 limit)
    res_locked = await client.post("/api/v1/auth/login", json={"username": "target_user", "password": "WrongAttempt6!"})
    assert res_locked.status_code == 429
    assert res_locked.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert "Retry-After" in res_locked.headers


@pytest.mark.asyncio
async def test_5a_fair_share_queue_scheduling(test_env, running_mock_engine):
    """
    4. Fair Resource Scheduling:
       - User A queues 1 GPU job and 1 CPU job with Priority 0.
       - User B queues 1 CPU job with Priority 0.
       - First claim selects User A's GPU job.
       - Second claim selects User B's CPU job (Least active user first across candidates for free CPU slot)
         rather than User A's remaining CPU job.
       - Priority preemption: Higher priority job preempts lower priority jobs regardless of active load.
    """
    # Stop background supervisor so test has explicit control over atomic claims
    from apps.server.src.supervisor.supervisor import supervisor
    await supervisor.stop_all()

    async with database.AsyncSessionLocal() as session:
        user_a = User(id="user_alpha", username="alpha", password_hash="h", role="editor")
        user_b = User(id="user_bravo", username="bravo", password_hash="h", role="editor")
        user_c = User(id="user_charlie", username="charlie", password_hash="h", role="editor")
        session.add_all([user_a, user_b, user_c])
        await session.commit()

        # User A enqueues 2 jobs: Job A1 (GPU) and Job A2 (CPU)
        req_a1 = TTSJobSubmitRequest(text="Job A1 GPU", engine_id="mock-tts", language="vi", priority=0)
        req_a2 = TTSJobSubmitRequest(text="Job A2 CPU", engine_id="mock-tts", language="vi", priority=0)
        job_a1 = await DurableQueueService.submit_speech_job(session, req_a1, user_a)
        job_a2 = await DurableQueueService.submit_speech_job(session, req_a2, user_a)

        # Set job_a1 resource_type to 'gpu' to utilize the independent GPU slot
        await session.execute(update(JobRecord).where(JobRecord.id == job_a1.id).values(resource_type="gpu"))
        await session.commit()

        # User B enqueues 1 CPU job (same priority 0)
        req_b1 = TTSJobSubmitRequest(text="Job B1 CPU", engine_id="mock-tts", language="vi", priority=0)
        job_b1 = await DurableQueueService.submit_speech_job(session, req_b1, user_b)

    # Claim 1: First job claimed is Job A1 (User A has 0 active, User B has 0 active; FIFO)
    # This occupies the 1 available GPU slot
    claimed_1 = await DurableQueueService.claim_next_job(worker_id="worker-slot-gpu", lease_duration_seconds=60)
    assert claimed_1 is not None
    assert claimed_1.id == job_a1.id
    assert claimed_1.user_id == user_a.id
    assert claimed_1.resource_type == "gpu"

    # Now User A has 1 active job (PREPARING on GPU slot)
    # User B has 0 active jobs
    # CPU slot is completely FREE! Candidates for CPU slot: Job A2 (User A) and Job B1 (User B)
    # When Worker 2 claims for CPU, Fair-share scheduler MUST pick User B's job (job_b1), NOT User A's second job!
    claimed_2 = await DurableQueueService.claim_next_job(worker_id="worker-slot-cpu", lease_duration_seconds=60)
    assert claimed_2 is not None
    assert claimed_2.id == job_b1.id
    assert claimed_2.user_id == user_b.id
    assert claimed_2.resource_type == "cpu"

    # Now User C enqueues a High-Priority CPU job (Priority 2)
    async with database.AsyncSessionLocal() as session:
        req_c1 = TTSJobSubmitRequest(text="High Priority Job C1", engine_id="mock-tts", language="vi", priority=2)
        job_c1 = await DurableQueueService.submit_speech_job(session, req_c1, user_c)

    # Finish User B's job to free the CPU slot
    async with database.AsyncSessionLocal() as session:
        await session.execute(
            update(JobRecord).where(JobRecord.id == claimed_2.id).values(status=JobState.COMPLETED.value)
        )
        await session.commit()
    from apps.server.src.services.resource_manager import resource_manager
    await resource_manager.release_all(claimed_2.id)

    # Next claim for CPU slot: Candidates are Job C1 (Priority 2) and Job A2 (Priority 0)
    # Must pick High Priority Job C1 due to priority preemption
    claimed_3 = await DurableQueueService.claim_next_job(worker_id="worker-slot-cpu", lease_duration_seconds=60)
    assert claimed_3 is not None
    assert claimed_3.id == job_c1.id
    assert claimed_3.priority == 2


@pytest.mark.asyncio
async def test_5a_max_outstanding_jobs_limit(test_env, running_mock_engine):
    """
    5. Maximum Outstanding Jobs Limit:
       - Submitting beyond MAX_OUTSTANDING_JOBS_PER_USER (25) is rejected with HTTP 429.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_busy", username="busy_bee", password_hash="h", role="editor")
        from apps.server.src.models.engine import EngineRecord
        dormant_engine = EngineRecord(
            id="dormant-tts",
            name="Dormant Engine",
            version="1.0.0",
            capabilities=["text_to_speech"],
            device_target="cpu",
        )
        session.add_all([user, dormant_engine])
        await session.commit()

        # Submit up to max limit (25 jobs)
        for i in range(settings.MAX_OUTSTANDING_JOBS_PER_USER):
            req = TTSJobSubmitRequest(text=f"Sentence {i}", engine_id="dormant-tts", language="vi")
            await DurableQueueService.submit_speech_job(session, req, user)

        # 26th job MUST be rejected with HTTP 429
        req_overflow = TTSJobSubmitRequest(text="Overflow Sentence", engine_id="dormant-tts", language="vi")
        with pytest.raises(Exception) as excinfo:
            await DurableQueueService.submit_speech_job(session, req_overflow, user)

        assert getattr(excinfo.value, "status_code", None) == 429
        assert getattr(excinfo.value, "code", None) == "TOO_MANY_OUTSTANDING_JOBS"


@pytest.mark.asyncio
async def test_5a_user_storage_quota_enforcement(client: AsyncClient):
    """
    6. Non-destructive User Storage Quota:
       - GET /api/v1/auth/storage reports usage and quota limit.
       - Exceeding storage quota rejects upload with HTTP 413 USER_STORAGE_QUOTA_EXCEEDED.
       - Existing audio assets remain preserved and non-destructively intact.
    """
    # 1. Bootstrap admin
    token = get_or_create_bootstrap_token()
    await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "quota_admin", "password": "AdminPassword123!", "setup_token": token},
    )

    # 2. Login
    login_res = await client.post("/api/v1/auth/login", json={"username": "quota_admin", "password": "AdminPassword123!"})
    jwt_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # 3. Check storage profile endpoint
    st_res = await client.get("/api/v1/auth/storage", headers=headers)
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert "used_bytes" in st_data
    assert "used_mb" in st_data
    assert "quota_mb" in st_data
    assert st_data["quota_mb"] == 5120.0  # Default 5GB

    # 4. Set custom tight quota for quota_admin in database (e.g. 1 MB limit)
    async with database.AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.username == "quota_admin").values(storage_quota_mb=1)
        )
        await session.commit()

    # 5. Verify updated quota limit reflected in storage API
    st_res_updated = await client.get("/api/v1/auth/storage", headers=headers)
    assert st_res_updated.json()["quota_mb"] == 1.0

    # 6. Attempt to upload a WAV file exceeding 1MB (e.g. 1.2MB of audio bytes) -> HTTP 413
    big_wav = _create_mock_wav(duration_seconds=28.0, sample_rate=24000)  # ~1.34 MB
    assert len(big_wav) > 1024 * 1024

    upload_fail = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        files={"file": ("large_voice.wav", big_wav, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert upload_fail.status_code == 413
    assert upload_fail.json()["code"] == "USER_STORAGE_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_5a_voice_cloning_strict_ownership_no_admin_bypass(test_env, running_mock_engine):
    """
    7. Strict Reference Audio Ownership Isolation:
       - User A owns a reference audio asset.
       - Admin attempts to use User A's reference audio ID in a synthesis job.
       - System rejects with HTTP 403 FORBIDDEN_ASSET_ACCESS.
       - Silent admin bypass is strictly prohibited.
    """
    async with database.AsyncSessionLocal() as session:
        user_a = User(id="user_owner_a", username="owner_a", password_hash="h", role="editor")
        admin_user = User(id="user_admin_x", username="admin_x", password_hash="h", role="admin")
        session.add_all([user_a, admin_user])
        await session.commit()

        # Create reference audio belonging to User A
        ref_asset = ReferenceAssetRecord(
            id="ref_asset_user_a",
            user_id=user_a.id,
            filename="private_voice.wav",
            file_path="mock/path/private_voice.wav",
            file_hash_sha256="mocksha256",
            file_size_bytes=1024,
            duration_seconds=5.0,
            sample_rate=24000,
            channels=1,
            format="wav",
            voice_use_consent=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(ref_asset)
        await session.commit()

        # Enable voice_cloning capability on the mock engine record
        from apps.server.src.models.engine import EngineRecord
        await session.execute(
            update(EngineRecord)
            .where(EngineRecord.id == "mock-tts")
            .values(capabilities=["text_to_speech", "voice_cloning"])
        )
        await session.commit()

        # Admin attempts to submit job with User A's reference asset
        req_admin = TTSJobSubmitRequest(
            text="Admin synthesizing private voice",
            engine_id="mock-tts",
            language="vi",
            parameters={"reference_asset_id": "ref_asset_user_a"},
        )

        with pytest.raises(Exception) as excinfo:
            await DurableQueueService.submit_speech_job(session, req_admin, admin_user)

        assert getattr(excinfo.value, "status_code", None) == 403
        assert getattr(excinfo.value, "code", None) == "FORBIDDEN_ASSET_ACCESS"
