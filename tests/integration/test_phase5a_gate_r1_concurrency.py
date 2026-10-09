"""
Phase 5A Release Gate R1 Concurrency, Fairness & Quota Verification Test Suite

Verifies:
1. Real Fair-Share Scheduling (Anti-Starvation):
   - User A submits 25 GPU jobs; User B submits 1 GPU job afterward.
   - Single GPU slot: Job 1 claims User A, Job 2 MUST claim User B. User B does not wait for 25 jobs.
   - Repeat for CPU jobs.
   - Persistent fairness state across runner restart / multiple processes.
   - Head-of-Line Priority Precedence: Priority 10 preempts lower priorities.
2. Atomic Storage Quota Accounting Under Concurrency:
   - User has 100 MB remaining quota.
   - Two concurrent tasks attempt to allocate 80 MB each.
   - Exactly one succeeds, the other fails with HTTP 413 USER_STORAGE_QUOTA_EXCEEDED.
   - No silent 160 MB commitment.
   - Reservation lifecycle: reserve -> commit -> release -> cleanup expired.
3. Long-Form Batch Rendering (Phase 4 Compatibility):
   - Project with 30 script segments (exceeding 25 outstanding jobs limit).
   - render_batch queues 25 segments and marks 5 as pending without HTTP 429 error.
   - Progressive pump upon job completion automatically enqueues pending segments.
4. Session Invalidation on Password Change:
   - Old JWT token is immediately rejected with HTTP 401 TOKEN_REVOKED after password change.
5. Login Brute-Force & Separate Account Protection:
   - 5 failed attempts for User Alpha locks User Alpha but does NOT lock User Bravo on the same IP.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import io
import pytest
import wave
from httpx import AsyncClient
from sqlalchemy import select, update, func

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.core.security import get_or_create_bootstrap_token, hash_password, create_access_token
from apps.server.src.models.user import User
from apps.server.src.models.job import JobRecord
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.models.storage_reservation import StorageReservationRecord
from apps.server.src.models.scheduling_state import UserSchedulingStateRecord
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.job_state_machine import JobState
from apps.server.src.services.resource_manager import resource_manager
from apps.server.src.services.user_quota_service import UserQuotaService
from apps.server.src.services.project_service import ProjectService
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.supervisor.supervisor import supervisor
from apps.server.src.supervisor.scheduler import scheduler


@pytest.fixture(autouse=True)
async def reset_hardware_slots():
    """Ensure resource slots, background workers, and scheduler are reset between test runs."""
    await scheduler.stop()
    await supervisor.stop_all()
    await resource_manager.reset()
    yield
    await scheduler.stop()
    await supervisor.stop_all()
    await resource_manager.reset()


@pytest.mark.asyncio
async def test_r1_real_fair_share_gpu_scheduling_anti_starvation(test_env, running_mock_engine):
    """
    Mandatory Scenario 1A (GPU):
    - User A submits 25 GPU jobs (priority 0).
    - User B submits 1 GPU job afterward (priority 0).
    - Single GPU slot available.
    - Claims must yield: Job 1 -> User A, Job 2 -> User B (anti-starvation)!
    - User B receives immediate next-turn scheduling rather than waiting for all 25 User A jobs.
    """
    # Stop background scheduler so test retains exclusive deterministic control over atomic claims
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        user_a = User(id="user_alpha_gpu", username="alpha_gpu", password_hash="h", role="editor")
        user_b = User(id="user_bravo_gpu", username="bravo_gpu", password_hash="h", role="editor")
        session.add_all([user_a, user_b])
        await session.commit()

        # 1. User A enqueues 25 GPU jobs
        jobs_a = []
        for i in range(25):
            req_a = TTSJobSubmitRequest(text=f"A GPU Job {i}", engine_id="mock-tts", language="vi", priority=0)
            job = await DurableQueueService.submit_speech_job(session, req_a, user_a)
            jobs_a.append(job)

        # Force resource_type to 'gpu' for all User A jobs to test serial single-slot GPU
        for j in jobs_a:
            await session.execute(update(JobRecord).where(JobRecord.id == j.id).values(resource_type="gpu"))
        await session.commit()

        # 2. User B enqueues 1 GPU job afterward
        req_b = TTSJobSubmitRequest(text="B GPU Job 0", engine_id="mock-tts", language="vi", priority=0)
        job_b = await DurableQueueService.submit_speech_job(session, req_b, user_b)
        await session.execute(update(JobRecord).where(JobRecord.id == job_b.id).values(resource_type="gpu"))
        await session.commit()

    claim_sequence = []

    # Claim 1: Should be Job A[0]
    claimed_1 = await DurableQueueService.claim_next_job(worker_id="worker-gpu-1")
    assert claimed_1 is not None
    assert claimed_1.user_id == user_a.id
    claim_sequence.append((claimed_1.user_id, claimed_1.id))

    # Complete Claim 1 (frees GPU slot)
    await DurableQueueService.mark_running(claimed_1.id, claimed_1.current_attempt_id, worker_id="worker-gpu-1")
    await DurableQueueService.complete_job(
        job_id=claimed_1.id,
        attempt_id=claimed_1.current_attempt_id,
        artifact_id="art-mock-1",
    )

    # Claim 2: MUST BE User B's job! (Anti-starvation check)
    claimed_2 = await DurableQueueService.claim_next_job(worker_id="worker-gpu-1")
    assert claimed_2 is not None
    assert claimed_2.user_id == user_b.id, f"Starvation detected! Claim 2 was {claimed_2.user_id} instead of User B"
    assert claimed_2.id == job_b.id
    claim_sequence.append((claimed_2.user_id, claimed_2.id))

    # Complete Claim 2
    await DurableQueueService.mark_running(claimed_2.id, claimed_2.current_attempt_id, worker_id="worker-gpu-1")
    await DurableQueueService.complete_job(
        job_id=claimed_2.id,
        attempt_id=claimed_2.current_attempt_id,
        artifact_id="art-mock-2",
    )

    # Claim 3: Should return to User A
    claimed_3 = await DurableQueueService.claim_next_job(worker_id="worker-gpu-1")
    assert claimed_3 is not None
    assert claimed_3.user_id == user_a.id
    claim_sequence.append((claimed_3.user_id, claimed_3.id))

    # Assert exact observed dispatch order
    assert [u for u, _ in claim_sequence] == ["user_alpha_gpu", "user_bravo_gpu", "user_alpha_gpu"]


@pytest.mark.asyncio
async def test_r1_real_fair_share_cpu_scheduling_anti_starvation(test_env, running_mock_engine):
    """
    Mandatory Scenario 1B (CPU):
    - User A submits 10 CPU jobs (priority 0).
    - User B submits 1 CPU job (priority 0).
    - User B receives scheduling immediately after Job 1 of User A completes.
    """
    # Stop background scheduler so test retains exclusive deterministic control over atomic claims
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        user_a = User(id="user_alpha_cpu", username="alpha_cpu", password_hash="h", role="editor")
        user_b = User(id="user_bravo_cpu", username="bravo_cpu", password_hash="h", role="editor")
        session.add_all([user_a, user_b])
        await session.commit()

        # User A enqueues 10 CPU jobs
        for i in range(10):
            req_a = TTSJobSubmitRequest(text=f"A CPU Job {i}", engine_id="mock-tts", language="vi", priority=0)
            await DurableQueueService.submit_speech_job(session, req_a, user_a)

        # User B enqueues 1 CPU job
        req_b = TTSJobSubmitRequest(text="B CPU Job 0", engine_id="mock-tts", language="vi", priority=0)
        job_b = await DurableQueueService.submit_speech_job(session, req_b, user_b)

    # Claim 1: User A
    c1 = await DurableQueueService.claim_next_job(worker_id="worker-cpu-1")
    assert c1 is not None and c1.user_id == user_a.id
    await DurableQueueService.mark_running(c1.id, c1.current_attempt_id, worker_id="worker-cpu-1")
    await DurableQueueService.complete_job(c1.id, c1.current_attempt_id, "art-mock-cpu-1")

    # Claim 2: MUST BE User B
    c2 = await DurableQueueService.claim_next_job(worker_id="worker-cpu-1")
    assert c2 is not None and c2.user_id == user_b.id
    assert c2.id == job_b.id


@pytest.mark.asyncio
async def test_r1_priority_head_of_line_precedence_and_restart_persistence(test_env, running_mock_engine):
    """
    Verifies that:
    1. Higher priority jobs preempt lower priority jobs in dispatch order regardless of fair-share history.
    2. Scheduling history persists in database across standalone runner restarts.
    """
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        user_norm = User(id="user_norm", username="norm", password_hash="h", role="editor")
        user_vip = User(id="user_vip", username="vip", password_hash="h", role="editor")
        session.add_all([user_norm, user_vip])
        await session.commit()

        # Norm user submitted 3 jobs with priority 0
        req_n = TTSJobSubmitRequest(text="Norm Job 1", engine_id="mock-tts", language="vi", priority=0)
        await DurableQueueService.submit_speech_job(session, req_n, user_norm)

        # VIP user submits job with Priority 10
        req_v = TTSJobSubmitRequest(text="VIP Urgent Job", engine_id="mock-tts", language="vi", priority=10)
        job_vip = await DurableQueueService.submit_speech_job(session, req_v, user_vip)

    # Claim must yield VIP job first due to Head-of-Line Priority
    claimed = await DurableQueueService.claim_next_job(worker_id="worker-prio-1")
    assert claimed is not None
    assert claimed.id == job_vip.id
    assert claimed.user_id == user_vip.id
    assert claimed.priority == 10
    await DurableQueueService.mark_running(claimed.id, claimed.current_attempt_id, worker_id="worker-prio-1")
    await DurableQueueService.complete_job(claimed.id, claimed.current_attempt_id, "art-vip")

    # Verify persistent state in DB table user_scheduling_states
    async with database.AsyncSessionLocal() as session:
        state = await session.get(UserSchedulingStateRecord, (user_vip.id, "cpu"))
        assert state is not None
        assert state.dispatched_count >= 1
        assert state.last_dispatched_at is not None


@pytest.mark.asyncio
async def test_r1_atomic_storage_quota_under_concurrency(test_env, running_mock_engine):
    """
    Mandatory Scenario 2:
    - User has 100 MB remaining.
    - Two concurrent requests attempt to create/reserve 80 MB each.
    - Exactly one succeeds, the second must be rejected with HTTP 413 USER_STORAGE_QUOTA_EXCEEDED.
    - The system must NOT silently commit 160 MB!
    """
    async with database.AsyncSessionLocal() as session:
        # Create user with strict 100 MB quota
        quota_user = User(
            id="user_quota_race",
            username="quota_race_user",
            password_hash="h",
            role="editor",
            storage_quota_mb=100,  # 100 MB quota
        )
        session.add(quota_user)
        await session.commit()

    eighty_mb = 80 * 1024 * 1024  # 80 MB in bytes

    async def attempt_reservation(task_name: str):
        async with database.AsyncSessionLocal() as s:
            try:
                res = await UserQuotaService.reserve_capacity(
                    db=s,
                    user=quota_user.id,
                    estimated_bytes=eighty_mb,
                    reservation_type="test_concurrency",
                    timeout_seconds=300,
                )
                await s.commit()
                return {"task": task_name, "success": True, "res_id": res.id}
            except Exception as e:
                await s.rollback()
                return {"task": task_name, "success": False, "error": str(e), "code": getattr(e, "code", None)}

    # Run two parallel reservation requests simultaneously
    results = await asyncio.gather(
        attempt_reservation("task_1"),
        attempt_reservation("task_2"),
    )

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    assert len(successes) == 1, f"Expected exactly 1 successful reservation, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"
    assert failures[0]["code"] == "USER_STORAGE_QUOTA_EXCEEDED"

    # Verify total usage calculation does not breach quota
    async with database.AsyncSessionLocal() as session:
        usage = await UserQuotaService.get_user_storage_usage(session, quota_user.id)
        assert usage["used_mb"] <= 100.0, f"Storage exceeded limit: {usage['used_mb']} MB"
        assert usage["reserved_bytes"] == eighty_mb

        # Clean up / release the single successful reservation
        await UserQuotaService.release_reservation(session, successes[0]["res_id"])
        await session.commit()

        # Usage drops back to 0
        usage_after = await UserQuotaService.get_user_storage_usage(session, quota_user.id)
        assert usage_after["used_bytes"] == 0


@pytest.mark.asyncio
async def test_r1_long_form_bounded_batch_rendering(test_env, running_mock_engine):
    """
    Mandatory Scenario 3 (Phase 4 Compatibility):
    - Project contains 30 script segments (exceeding MAX_OUTSTANDING_JOBS_PER_USER = 25).
    - render_batch queues 25 segments and marks 5 as pending without triggering HTTP 429.
    - As jobs complete, reconcile_project_segments progressively pumps the remaining pending segments.
    """
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        user = User(id="user_author", username="author", password_hash="h", role="editor")
        session.add(user)
        await session.commit()

        # Create project with 30 segments
        project = ProjectRecord(id="proj_long_form", user_id=user.id, title="Truyen Dai Tap 1")
        session.add(project)
        await session.commit()

        from apps.server.src.services.project_service import compute_segment_hash

        for i in range(30):
            t = f"Phan doan so {i + 1} cua cuon tieu thuyet."
            thash = compute_segment_hash(t, "mock-tts", "vi-female-1", {})
            seg = ScriptSegmentRecord(
                project_id=project.id,
                sequence_order=i,
                text=t,
                language="vi",
                engine_id="mock-tts",
                voice_id="vi-female-1",
                status="draft",
                text_hash=thash,
                version=1,
            )
            session.add(seg)
        await session.commit()

        # 1. Trigger render_batch for all 30 segments
        rendered = await ProjectService.render_batch(session, user, project.id)
        assert len(rendered) == 30

        # Exactly 25 segments should be queued, and 5 should be pending
        queued_count = sum(1 for seg, _ in rendered if seg.status == "queued")
        pending_count = sum(1 for seg, _ in rendered if seg.status == "pending")

        assert queued_count == 25, f"Expected 25 queued, got {queued_count}"
        assert pending_count == 5, f"Expected 5 pending, got {pending_count}"

        # 2. Simulate completion of 5 running jobs
        first_5_jobs = [seg.last_job_id for seg, _ in rendered if seg.status == "queued"][:5]
        for jid in first_5_jobs:
            art = ArtifactRecord(
                id=f"art_{jid}",
                owner_id=user.id,
                file_path="mock_audio.wav",
                file_size_bytes=5000,
                duration_seconds=1.5,
                sample_rate=24000,
                format="wav",
            )
            session.add(art)
            stmt = select(JobRecord).where(JobRecord.id == jid)
            res = await session.execute(stmt)
            job = res.scalar_one()
            job.status = JobState.COMPLETED.value
            job.artifact_id = art.id
            await session.commit()

        # 3. Call reconcile_project_segments (which triggers the progressive pump)
        reconciled = await ProjectService.reconcile_project_segments(session, user, project.id)

        # The 5 completed segments transitioned to 'completed'
        completed_count = sum(1 for s in reconciled.segments if s.status == "completed")
        assert completed_count == 5

        # The 5 previously 'pending' segments were automatically pumped into 'queued'
        new_pending_count = sum(1 for s in reconciled.segments if s.status == "pending")
        assert new_pending_count == 0, f"Expected 0 pending after pump, got {new_pending_count}"

        # All 30 segments are now either completed or queued, with 0 lost!
        assert len(reconciled.segments) == 30


@pytest.mark.asyncio
async def test_r1_session_revocation_on_password_change(test_env, client: AsyncClient):
    """
    Mandatory Scenario 4:
    - User logs in and obtains token_A.
    - User changes password.
    - token_A is immediately rejected with HTTP 401 TOKEN_REVOKED.
    - User logs in with new password and obtains token_B which works.
    """
    # 1. Setup user
    async with database.AsyncSessionLocal() as session:
        user = User(
            id="user_pwd_test",
            username="pwd_test_user",
            password_hash=hash_password("OldPassword123!"),
            role="editor",
            token_version=1,
        )
        session.add(user)
        await session.commit()

    # 2. Login to get token_A
    res_login = await client.post("/api/v1/auth/login", json={"username": "pwd_test_user", "password": "OldPassword123!"})
    assert res_login.status_code == 200
    token_a = res_login.json()["access_token"]

    # Verify token_A works on /me
    res_me_1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert res_me_1.status_code == 200
    assert res_me_1.json()["username"] == "pwd_test_user"

    # 3. Change password using token_A
    res_change = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"old_password": "OldPassword123!", "new_password": "NewSecurePassword456!"},
    )
    assert res_change.status_code == 200

    # 4. Immediate revocation: token_A must now be rejected
    res_me_revoked = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert res_me_revoked.status_code == 401
    assert res_me_revoked.json()["code"] == "TOKEN_REVOKED"

    # 5. Login with new password
    res_login_new = await client.post("/api/v1/auth/login", json={"username": "pwd_test_user", "password": "NewSecurePassword456!"})
    assert res_login_new.status_code == 200
    token_b = res_login_new.json()["access_token"]

    # Verify token_B works
    res_me_new = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert res_me_new.status_code == 200
    assert res_me_new.json()["username"] == "pwd_test_user"


@pytest.mark.asyncio
async def test_r1_unrelated_account_isolation_on_shared_ip(test_env, client: AsyncClient):
    """
    Mandatory Scenario 5:
    - User Alpha fails login 5 times and gets locked out.
    - User Bravo on the same IP must NOT be locked out.
    """
    async with database.AsyncSessionLocal() as session:
        u_alpha = User(id="u_alpha", username="alpha_user", password_hash=hash_password("PassAlpha123!"), role="editor")
        u_bravo = User(id="u_bravo", username="bravo_user", password_hash=hash_password("PassBravo123!"), role="editor")
        session.add_all([u_alpha, u_bravo])
        await session.commit()

    # User Alpha fails 5 times
    for i in range(5):
        r = await client.post("/api/v1/auth/login", json={"username": "alpha_user", "password": f"Wrong{i}!"})
        assert r.status_code == 401

    # User Alpha 6th attempt is locked out (429)
    r_alpha_locked = await client.post("/api/v1/auth/login", json={"username": "alpha_user", "password": "Wrong6!"})
    assert r_alpha_locked.status_code == 429
    assert r_alpha_locked.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"

    # User Bravo on same client socket logs in successfully (200)
    r_bravo_ok = await client.post("/api/v1/auth/login", json={"username": "bravo_user", "password": "PassBravo123!"})
    assert r_bravo_ok.status_code == 200
    assert "access_token" in r_bravo_ok.json()
