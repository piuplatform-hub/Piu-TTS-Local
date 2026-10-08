"""
Phase 2 Comprehensive Test Suite: Durable Job Orchestration & Production Resilience
Covers 14 integration test matrix items:
1. State machine transitions
2. Atomic claiming concurrency
3. Idempotency & payload conflict
4. Lease expiration reclaiming
5. Fencing token rejection
6. Retry with exponential backoff
7. Manual retry of failed jobs
8. Cancellation of queued & running jobs
9. Server restart recovery
10. Resource limits & slot waiting reasons
11. SSE event ordering and Last-Event-ID replay
12. SSE query parameter token authentication
13. Short SQLite transactions without synthesis locking
14. Artifact isolation on cancellation
"""

import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select

from apps.server.src import database
from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src.models.job import JobRecord, JobEventRecord
from apps.server.src.models.user import User
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.durable_queue_service import (
    DurableQueueService,
    FencingTokenError,
)
from apps.server.src.services.job_state_machine import (
    JobStateMachine,
    JobState,
    IllegalStateTransitionError,
)
from apps.server.src.services.resource_manager import resource_manager
from apps.server.src.services.event_service import event_service
from apps.server.src.core.errors import AppException


@pytest.mark.asyncio
async def test_01_job_state_machine_valid_and_invalid_transitions():
    """1. State machine: all valid transitions succeed, invalid transitions raise error."""
    # Valid transitions
    JobStateMachine.validate_transition(JobState.QUEUED.value, JobState.PREPARING.value)
    JobStateMachine.validate_transition(JobState.PREPARING.value, JobState.RUNNING.value)
    JobStateMachine.validate_transition(JobState.RUNNING.value, JobState.COMPLETED.value)
    JobStateMachine.validate_transition(JobState.RUNNING.value, JobState.QUEUED.value)
    JobStateMachine.validate_transition(JobState.RUNNING.value, JobState.FAILED.value)
    JobStateMachine.validate_transition(JobState.FAILED.value, JobState.QUEUED.value)
    JobStateMachine.validate_transition(JobState.QUEUED.value, JobState.CANCELLED.value)
    JobStateMachine.validate_transition(JobState.RUNNING.value, JobState.CANCELLED.value)

    # Invalid transitions
    with pytest.raises(IllegalStateTransitionError):
        JobStateMachine.validate_transition(JobState.COMPLETED.value, JobState.RUNNING.value)

    with pytest.raises(IllegalStateTransitionError):
        JobStateMachine.validate_transition(JobState.CANCELLED.value, JobState.RUNNING.value)

    with pytest.raises(IllegalStateTransitionError):
        JobStateMachine.validate_transition(JobState.QUEUED.value, JobState.COMPLETED.value)


@pytest.mark.asyncio
async def test_02_atomic_claim_concurrency(test_env, running_mock_engine):
    """2. Atomic claim: concurrent workers cannot claim the same job."""
    async with database.AsyncSessionLocal() as session:
        # Create a test user
        user = User(id="user_concurrency", username="concurrent_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        # Enqueue 1 job
        req = TTSJobSubmitRequest(
            text="Kiểm tra atomic claim",
            engine_id="mock-tts",
            language="vi",
            priority=5,
        )
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    # Simulate 10 workers attempting to claim the single job concurrently
    async def worker_claim(worker_num: int):
        return await DurableQueueService.claim_next_job(worker_id=f"worker-{worker_num}", lease_duration_seconds=30)

    claims = await asyncio.gather(*(worker_claim(i) for i in range(10)))
    claimed_jobs = [c for c in claims if c is not None]

    assert len(claimed_jobs) == 1, f"Expected exactly 1 claim, got {len(claimed_jobs)}"
    assert claimed_jobs[0].id == job_id
    assert claimed_jobs[0].attempt_count == 1
    assert claimed_jobs[0].status == "preparing"
    assert claimed_jobs[0].current_attempt_id is not None

    # Clean up resource slot
    await resource_manager.release_all(job_id)


@pytest.mark.asyncio
async def test_03_idempotency_payload_conflict(test_env, running_mock_engine):
    """3. Idempotency: duplicate submission returns existing job; different payload returns 409."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_idem", username="idem_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req1 = TTSJobSubmitRequest(
            text="Same text",
            engine_id="mock-tts",
            language="vi",
            idempotency_key="idem-key-unique-01",
        )
        job1 = await DurableQueueService.submit_speech_job(session, req1, user)

        # Resubmit with exact same payload -> returns job1
        job2 = await DurableQueueService.submit_speech_job(session, req1, user)
        assert job2.id == job1.id

        # Resubmit with same key but DIFFERENT text -> 409 Conflict
        req_diff = TTSJobSubmitRequest(
            text="Different text completely",
            engine_id="mock-tts",
            language="vi",
            idempotency_key="idem-key-unique-01",
        )
        with pytest.raises(AppException) as exc_info:
            await DurableQueueService.submit_speech_job(session, req_diff, user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_04_lease_expiration_and_reclaiming(test_env, running_mock_engine):
    """4. Lease expiration: job with expired lease is reclaimed by another worker."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_lease", username="lease_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Lease test", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)

    # Claim job with expired lease (0 seconds)
    claimed = await DurableQueueService.claim_next_job(worker_id="worker-fast", lease_duration_seconds=-5)
    assert claimed is not None
    assert claimed.status == "preparing"

    # Trigger lease reclaiming
    reclaimed_count = await DurableQueueService.reclaim_expired_leases()
    assert reclaimed_count == 1

    # Check job state in DB
    async with database.AsyncSessionLocal() as session:
        res = await session.execute(select(JobRecord).where(JobRecord.id == claimed.id))
        reclaimed_job = res.scalar_one()
        assert reclaimed_job.status == "queued"
        assert reclaimed_job.attempt_count == 1
        assert "Reclaimed" in (reclaimed_job.waiting_reason or "")

    # Clean up to prevent background scheduler from picking up during teardown
    await DurableQueueService.cancel_job(claimed.id, user)


@pytest.mark.asyncio
async def test_05_fencing_token_rejection(test_env, running_mock_engine):
    """5. Fencing token: stale worker completion is rejected after lease expiration."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_fencing", username="fencing_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Fencing test", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)

    # Worker 1 claims job
    claimed_1 = await DurableQueueService.claim_next_job(worker_id="worker-1", lease_duration_seconds=-5)
    stale_attempt_id = claimed_1.current_attempt_id

    # Lease expires and is reclaimed
    await DurableQueueService.reclaim_expired_leases()

    # Worker 2 claims job with new attempt token
    # Manually adjust scheduled_at so it's immediately ready
    async with database.AsyncSessionLocal() as session:
        res = await session.execute(select(JobRecord).where(JobRecord.id == claimed_1.id))
        j = res.scalar_one()
        j.scheduled_at = None
        await session.commit()

    claimed_2 = await DurableQueueService.claim_next_job(worker_id="worker-2", lease_duration_seconds=30)
    assert claimed_2.current_attempt_id != stale_attempt_id

    # Worker 1 (stale) attempts to commit completion -> MUST BE REJECTED
    with pytest.raises(FencingTokenError):
        await DurableQueueService.complete_job(
            job_id=claimed_1.id,
            attempt_id=stale_attempt_id,
            artifact_id="fake-stale-artifact",
        )

    # Clean up
    await DurableQueueService.cancel_job(claimed_1.id, user)
    await resource_manager.release_all(claimed_1.id)


@pytest.mark.asyncio
async def test_06_retry_with_exponential_backoff(test_env, running_mock_engine):
    """6. Retry with backoff: failing job retries up to max_retries with delays, then fails."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_retry", username="retry_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Retry backoff", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    # Claim attempt 1
    c1 = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert c1.attempt_count == 1

    # Transient failure 1 -> should backoff and return to queued
    await DurableQueueService.fail_job(job_id, c1.current_attempt_id, "NETWORK_ERR", "Transient", retryable=True)

    async with database.AsyncSessionLocal() as session:
        j = (await session.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert j.status == "queued"
        assert j.scheduled_at is not None
        # Reset scheduled_at for test speed
        j.scheduled_at = None
        await session.commit()

    # Claim attempt 2
    c2 = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert c2.attempt_count == 2
    await DurableQueueService.fail_job(job_id, c2.current_attempt_id, "NETWORK_ERR", "Transient", retryable=True)

    async with database.AsyncSessionLocal() as session:
        j = (await session.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert j.status == "queued"
        j.scheduled_at = None
        await session.commit()

    # Claim attempt 3 (max_retries = 3)
    c3 = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert c3.attempt_count == 3

    # Attempt 3 fails -> retry budget exhausted, becomes permanently FAILED
    await DurableQueueService.fail_job(job_id, c3.current_attempt_id, "NETWORK_ERR", "Exhausted", retryable=True)

    async with database.AsyncSessionLocal() as session:
        j = (await session.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert j.status == "failed"
        assert j.error_details["code"] == "NETWORK_ERR"


@pytest.mark.asyncio
async def test_07_manual_retry_of_failed_job(test_env, running_mock_engine):
    """7. Manual retry: failed job can be manually retried, resetting state to queued."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_manual", username="manual_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Manual retry", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    c = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    # Fail permanently
    await DurableQueueService.fail_job(job_id, c.current_attempt_id, "FATAL", "Unrecoverable", retryable=False)

    # User manually retries
    retried = await DurableQueueService.retry_failed_job(job_id, user)
    assert retried.status == "queued"
    assert retried.attempt_count == 0
    assert retried.error_details is None


@pytest.mark.asyncio
async def test_08_cancellation_queued_and_running(test_env, running_mock_engine):
    """8. Cancellation: cancelling queued cancels immediately; cancelling running interrupts worker."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_cancel", username="cancel_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Cancel queued", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)

    # 8a. Cancel while queued
    cancelled_queued = await DurableQueueService.cancel_job(job.id, user)
    assert cancelled_queued.status == "cancelled"

    # 8b. Cancel while running
    async with database.AsyncSessionLocal() as session:
        req2 = TTSJobSubmitRequest(text="Cancel running", engine_id="mock-tts", language="vi")
        job2 = await DurableQueueService.submit_speech_job(session, req2, user)

    claimed = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    cancelled_running = await DurableQueueService.cancel_job(claimed.id, user)
    assert cancelled_running.status == "cancelled"

    # 8c. Cannot cancel completed job
    cancelled_running.status = "completed"
    async with database.AsyncSessionLocal() as session:
        session.add(cancelled_running)
        await session.commit()

    with pytest.raises(AppException) as exc:
        await DurableQueueService.cancel_job(cancelled_running.id, user)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_09_server_restart_recovery(test_env, running_mock_engine):
    """9. Server restart recovery: simulated restart reclaims stuck jobs."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_restart", username="restart_u", password_hash="hash", role="editor")
        session.add(user)

        # Simulate job stranded in running state with attempt_count = 1
        stuck_1 = JobRecord(
            id="stuck_1",
            user_id=user.id,
            engine_id="mock-tts",
            status="running",
            attempt_count=1,
            max_retries=3,
            queued_at=datetime.now(timezone.utc),
        )
        # Simulate job stranded in preparing state with attempt_count = 3 (budget exhausted)
        stuck_2 = JobRecord(
            id="stuck_2",
            user_id=user.id,
            engine_id="mock-tts",
            status="preparing",
            attempt_count=3,
            max_retries=3,
            queued_at=datetime.now(timezone.utc),
        )
        session.add_all([stuck_1, stuck_2])
        await session.commit()

    recovered_count = await DurableQueueService.recover_on_startup()
    assert recovered_count == 2

    async with database.AsyncSessionLocal() as session:
        j1 = (await session.execute(select(JobRecord).where(JobRecord.id == "stuck_1"))).scalar_one()
        assert j1.status == "queued"
        assert "Recovered" in (j1.waiting_reason or "")

        j2 = (await session.execute(select(JobRecord).where(JobRecord.id == "stuck_2"))).scalar_one()
        assert j2.status == "failed"
        assert j2.error_details["code"] == "SERVER_RESTARTED"


@pytest.mark.asyncio
async def test_10_resource_limits_and_waiting_reason(test_env, running_mock_engine):
    """10. Resource limits: GPU slot limit prevents concurrent GPU jobs; queued jobs wait with reason."""
    await resource_manager.reset()

    # Manually occupy GPU slot
    assert await resource_manager.acquire("gpu", "active-gpu-job") is True
    assert await resource_manager.can_acquire("gpu") is False

    async with database.AsyncSessionLocal() as session:
        user = User(id="user_res", username="res_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        # Enqueue GPU job
        req = TTSJobSubmitRequest(text="GPU job", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)
        # Explicitly tag as GPU resource
        job.resource_type = "gpu"
        await session.commit()

    # Worker attempts claim -> should be blocked by GPU slot and set waiting_reason
    claimed = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert claimed is None

    async with database.AsyncSessionLocal() as session:
        j = (await session.execute(select(JobRecord).where(JobRecord.id == job.id))).scalar_one()
        assert j.status == "queued"
        assert "Awaiting GPU slot" in (j.waiting_reason or "")

    # Release GPU slot
    await resource_manager.release("gpu", "active-gpu-job")

    # Now worker can claim it
    claimed_now = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert claimed_now is not None
    assert claimed_now.id == job.id

    await resource_manager.release_all(job.id)


@pytest.mark.asyncio
async def test_11_sse_event_streaming_and_replay(test_env, running_mock_engine):
    """11. SSE streaming: events received in order; Last-Event-ID replays missed events."""
    job_id = "job-sse-test-11"
    async with database.AsyncSessionLocal() as session:
        # Emit 3 distinct events
        ev1 = await event_service.emit_event(session, job_id, "status_change", {"status": "queued"})
        ev2 = await event_service.emit_event(session, job_id, "progress", {"percent": 50})
        ev3 = await event_service.emit_event(session, job_id, "completed", {"status": "completed"})
        await session.commit()

    # Subscriber with last_event_id=ev1.id should replay ev2 and ev3
    events = []
    async for event in event_service.subscribe(job_id, last_event_id=ev1.id):
        events.append(event)

    assert len(events) == 2
    assert events[0]["event_type"] == "progress"
    assert events[1]["event_type"] == "completed"


@pytest.mark.asyncio
async def test_12_sse_query_param_authentication(client, running_mock_engine):
    """12. SSE auth: query param token authentication works for EventSource."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "sse_admin", "password": "Password12345!", "setup_token": token},
    )
    jwt_token = boot_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # Create a job
    job_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={"text": "SSE Auth", "engine_id": "mock-tts", "language": "vi"},
    )
    job_id = job_res.json()["id"]

    # Access SSE stream via query parameter ?token=... (no Authorization header)
    sse_res = await client.get(f"/api/v1/jobs/{job_id}/events?token={jwt_token}")
    assert sse_res.status_code == 200
    assert "text/event-stream" in sse_res.headers.get("content-type", "")

    # Access with invalid token -> 401
    bad_sse = await client.get(f"/api/v1/jobs/{job_id}/events?token=invalid_token")
    assert bad_sse.status_code == 401


@pytest.mark.asyncio
async def test_13_short_transactions_db_not_locked(test_env, running_mock_engine):
    """13. Short transactions: SQLite database not locked during worker synthesis."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_short", username="short_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Short tx", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)

    # Claim job
    claimed = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    assert claimed is not None

    # Simulate worker inference in parallel with concurrent database read/write
    async def concurrent_db_writer():
        for i in range(5):
            async with database.AsyncSessionLocal() as session:
                new_user = User(id=f"u_{i}", username=f"user_{i}", password_hash="h", role="editor")
                session.add(new_user)
                await session.commit()
            await asyncio.sleep(0.01)

    # Both concurrent writer and heartbeat run simultaneously without database locking errors
    await asyncio.gather(
        concurrent_db_writer(),
        DurableQueueService.heartbeat(claimed.id, claimed.current_attempt_id, extend_seconds=30),
    )

    await resource_manager.release_all(claimed.id)


@pytest.mark.asyncio
async def test_14_artifact_isolation_on_cancellation(test_env, running_mock_engine):
    """14. Artifact cleanup: cancelled jobs don't leave active published artifacts."""
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_isolate", username="isolate_u", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(text="Isolate artifact", engine_id="mock-tts", language="vi")
        job = await DurableQueueService.submit_speech_job(session, req, user)

    claimed = await DurableQueueService.claim_next_job(worker_id="w", lease_duration_seconds=30)
    # User cancels job
    await DurableQueueService.cancel_job(claimed.id, user)

    # Worker finishes later and attempts complete_job
    completed = await DurableQueueService.complete_job(
        job_id=claimed.id,
        attempt_id=claimed.current_attempt_id,
        artifact_id="artifact-cancelled",
    )
    # Must return False and not publish completed artifact
    assert completed is False

    async with database.AsyncSessionLocal() as session:
        j = (await session.execute(select(JobRecord).where(JobRecord.id == claimed.id))).scalar_one()
        assert j.status == "cancelled"
        assert j.artifact_id is None
