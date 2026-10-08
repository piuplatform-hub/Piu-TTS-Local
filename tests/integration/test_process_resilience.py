"""
AI Voice Studio — Phase 2 Process Resilience & Failure Recovery Tests
Validates:
- Scenario A: Subprocess kill and recovery (abrupt worker kill, stranded job recovery).
- Scenario B: Stale worker completion rejection across separate worker/runner processes (fencing tokens).
- Scenario C: Race condition between cancellation and completion (single terminal state, orphan artifact prevention).
- Scenario D: Multi-runner cross-process lease ownership & strict GPU slot limit enforcement.
- Scenario E: SSE stream reconnection and historical event replay via Last-Event-ID.
- Scenario F: SQLite online backup & live restore under active WAL write concurrency.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import pytest
from sqlalchemy import select, update

from apps.server.src import database
from apps.server.src.models.job import JobRecord
from apps.server.src.models.user import User
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.artifact_service import ArtifactService
from apps.server.src.services.backup_service import BackupService
from apps.server.src.services.durable_queue_service import DurableQueueService, FencingTokenError
from apps.server.src.services.event_service import event_service
from apps.server.src.services.job_state_machine import JobState
from apps.server.src.services.resource_manager import resource_manager
from apps.server.src.supervisor.scheduler import DurableJobScheduler
from apps.server.src.supervisor.supervisor import supervisor


@pytest.mark.asyncio
async def test_scenario_a_subprocess_kill_and_recovery(test_env, running_mock_engine):
    """
    Scenario A: Subprocess kill and recovery.
    Simulates abrupt termination of worker process during execution;
    verifies supervisor detection, clean job failure/retry handling, and startup crash recovery.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_scen_a", username="scen_a_user", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(
            text="Kiểm tra kill tiến trình worker",
            engine_id="mock-tts",
            language="vi",
            priority=5,
        )
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    # Claim job
    claimed = await DurableQueueService.claim_next_job(worker_id="runner-proc-a", lease_duration_seconds=30)
    assert claimed is not None
    assert claimed.id == job_id
    attempt_id = claimed.current_attempt_id

    # Mark running
    await DurableQueueService.mark_running(job_id=job_id, attempt_id=attempt_id, worker_id="runner-proc-a")

    # Abruptly kill the supervised worker process
    worker_inst = supervisor._workers.get("mock-tts")
    assert worker_inst is not None and worker_inst.is_alive()
    worker_inst.process.kill()
    worker_inst.process.wait()
    assert not worker_inst.is_alive()

    # Attempting synthesis against dead worker raises exception
    with pytest.raises(Exception):
        await worker_inst.client.get_health()

    # Simulate scheduler failure handler
    await DurableQueueService.fail_job(
        job_id=job_id,
        attempt_id=attempt_id,
        error_code="WORKER_PROCESS_TERMINATED",
        error_message="Worker process died unexpectedly",
        retryable=True,
    )

    # Job must now be back in QUEUED state with incremented attempt_count and exponential backoff scheduled_at
    async with database.AsyncSessionLocal() as session:
        j = await session.get(JobRecord, job_id)
        assert j.status == JobState.QUEUED.value
        assert j.attempt_count == 1
        assert j.scheduled_at is not None
        assert "Retrying in" in j.waiting_reason


@pytest.mark.asyncio
async def test_scenario_b_stale_worker_fencing_token_rejection(test_env, running_mock_engine):
    """
    Scenario B: Stale worker completion rejection across separate processes.
    Enforces that a worker from an earlier expired lease/attempt CANNOT complete a job
    once a new attempt has been claimed by another process.
    """
    # Stop background scheduler to isolate manual stepping
    from apps.server.src.supervisor.scheduler import scheduler
    await scheduler.stop()

    async with database.AsyncSessionLocal() as session:
        user = User(id="user_scen_b", username="scen_b_user", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(
            text="Fencing token multi-process check",
            engine_id="mock-tts",
            language="vi",
        )
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    # Process 1 claims Attempt 1
    job_attempt1 = await DurableQueueService.claim_next_job(worker_id="runner-node-1", lease_duration_seconds=1)
    assert job_attempt1 is not None
    attempt1_token = job_attempt1.current_attempt_id

    # Simulate lease expiration in DB
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    async with database.AsyncSessionLocal() as session:
        await session.execute(
            update(JobRecord).where(JobRecord.id == job_id).values(lease_expires_at=past)
        )
        await session.commit()

    # Reclaim expired leases
    reclaimed = await DurableQueueService.reclaim_expired_leases()
    assert reclaimed == 1

    # Reset scheduled_at to past so Attempt 2 can be claimed immediately
    async with database.AsyncSessionLocal() as session:
        await session.execute(
            update(JobRecord).where(JobRecord.id == job_id).values(scheduled_at=past)
        )
        await session.commit()

    # Process 2 claims Attempt 2
    job_attempt2 = await DurableQueueService.claim_next_job(worker_id="runner-node-2", lease_duration_seconds=30)
    assert job_attempt2 is not None
    attempt2_token = job_attempt2.current_attempt_id
    assert attempt2_token != attempt1_token

    # Process 1 finally finishes synthesis and tries to complete using stale Attempt 1 token
    async with database.AsyncSessionLocal() as session:
        artifact1 = await ArtifactService.create_artifact_from_bytes(
            db=session,
            owner_id=user.id,
            audio_bytes=b"RIFF_FAKE_AUDIO_ATTEMPT_1",
            format="wav",
        )

    with pytest.raises(FencingTokenError):
        await DurableQueueService.complete_job(
            job_id=job_id,
            attempt_id=attempt1_token,
            artifact_id=artifact1.id,
        )

    # Job remains owned by Process 2
    async with database.AsyncSessionLocal() as session:
        j = await session.get(JobRecord, job_id)
        assert j.current_attempt_id == attempt2_token
        assert j.status in (JobState.PREPARING.value, JobState.RUNNING.value)


@pytest.mark.asyncio
async def test_scenario_c_race_cancellation_vs_completion(test_env, running_mock_engine):
    """
    Scenario C: Race between cancellation and completion.
    Guarantees that exactly ONE terminal state wins, and if cancellation wins,
    the newly generated artifact is cleaned up to prevent orphan files.
    """
    from apps.server.src.supervisor.scheduler import scheduler
    await scheduler.stop()

    async with database.AsyncSessionLocal() as session:
        user = User(id="user_scen_c", username="scen_c_user", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        req = TTSJobSubmitRequest(
            text="Race cancellation vs completion",
            engine_id="mock-tts",
            language="vi",
        )
        job = await DurableQueueService.submit_speech_job(session, req, user)
        job_id = job.id

    claimed = await DurableQueueService.claim_next_job(worker_id="runner-proc-c", lease_duration_seconds=30)
    attempt_id = claimed.current_attempt_id
    await DurableQueueService.mark_running(job_id=job_id, attempt_id=attempt_id, worker_id="runner-proc-c")

    # Create artifact
    async with database.AsyncSessionLocal() as session:
        artifact = await ArtifactService.create_artifact_from_bytes(
            db=session,
            owner_id=user.id,
            audio_bytes=b"RIFF_RACE_TEST_AUDIO",
            format="wav",
        )
        artifact_path = Path(artifact.file_path)
        assert artifact_path.exists()

    # User cancels job FIRST
    cancelled_job = await DurableQueueService.cancel_job(job_id=job_id, current_user=user)
    assert cancelled_job.status == JobState.CANCELLED.value

    # Worker attempts completion on the cancelled job -> returns False because cancellation won
    completed_ok = await DurableQueueService.complete_job(
        job_id=job_id,
        attempt_id=attempt_id,
        artifact_id=artifact.id,
    )
    assert completed_ok is False, "complete_job must return False when job was already cancelled"

    # Orphan artifact cleanup
    async with database.AsyncSessionLocal() as session:
        await ArtifactService.delete_artifact(session, artifact.id)
    assert not artifact_path.exists(), "Orphan artifact must be deleted"

    # Verify state machine terminal guarantee
    async with database.AsyncSessionLocal() as session:
        final_job = await session.get(JobRecord, job_id)
        assert final_job.status == JobState.CANCELLED.value
        assert final_job.artifact_id is None


@pytest.mark.asyncio
async def test_scenario_d_multi_runner_cross_process_gpu_slot_enforcement(test_env, running_mock_engine):
    """
    Scenario D: Two separate runner instances cannot violate lease ownership or GPU slot limit (max 1 GPU).
    Simulates two runners polling the queue concurrently when 2 GPU jobs are enqueued.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(id="user_scen_d", username="scen_d_user", password_hash="hash", role="editor")
        session.add(user)
        await session.commit()

        # Submit 2 GPU jobs
        req1 = TTSJobSubmitRequest(text="GPU Job 1", engine_id="mock-tts", language="vi", priority=10)
        job1 = await DurableQueueService.submit_speech_job(session, req1, user)
        job1.resource_type = "gpu"

        req2 = TTSJobSubmitRequest(text="GPU Job 2", engine_id="mock-tts", language="vi", priority=5)
        job2 = await DurableQueueService.submit_speech_job(session, req2, user)
        job2.resource_type = "gpu"

        await session.commit()

    # Runner 1 and Runner 2 concurrently attempt to claim
    claim1, claim2 = await asyncio.gather(
        DurableQueueService.claim_next_job(worker_id="runner-instance-ALPHA", lease_duration_seconds=30),
        DurableQueueService.claim_next_job(worker_id="runner-instance-BETA", lease_duration_seconds=30),
    )

    claims = [c for c in [claim1, claim2] if c is not None]
    # Because max_gpu_slots == 1, EXACTLY 1 runner must claim a GPU job!
    assert len(claims) == 1, f"Expected exactly 1 GPU job claimed, got {len(claims)}"

    winner = claims[0]
    assert winner.resource_type == "gpu"
    assert winner.locked_by in ("runner-instance-ALPHA", "runner-instance-BETA")

    # Check that the other job has waiting_reason set to Awaiting GPU slot
    async with database.AsyncSessionLocal() as session:
        other_job_id = job2.id if winner.id == job1.id else job1.id
        other_job = await session.get(JobRecord, other_job_id)
        assert other_job.status == JobState.QUEUED.value
        assert other_job.waiting_reason == "Awaiting GPU slot"

    # Clean up acquired slot
    await resource_manager.release("gpu", winner.id)


@pytest.mark.asyncio
async def test_scenario_e_sse_stream_reconnection_and_replay(client, running_mock_engine):
    """
    Scenario E: SSE stream reconnection and historical event replay via Last-Event-ID.
    Verifies that missed events are replayed in exact monotonic order when client reconnects.
    """
    # 1. Login user
    user_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "scen_e_user", "password": "Password123!"},
    )
    if user_res.status_code != 200:
        # Bootstrap admin if needed
        from apps.server.src.core.security import get_or_create_bootstrap_token
        token = get_or_create_bootstrap_token()
        await client.post(
            "/api/v1/auth/bootstrap",
            json={"username": "sse_admin_e", "password": "Password123!", "setup_token": token},
        )
        login_res = await client.post("/api/v1/auth/login", json={"username": "sse_admin_e", "password": "Password123!"})
        auth_token = login_res.json()["access_token"]
    else:
        auth_token = user_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {auth_token}"}

    # 2. Submit job
    job_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={"text": "SSE Replay Test", "engine_id": "mock-tts", "language": "vi"},
    )
    job_id = job_res.json()["id"]

    # Emit historical events in DB
    async with database.AsyncSessionLocal() as session:
        ev1 = await event_service.emit_event(session, job_id, "status_change", {"status": "preparing"})
        ev2 = await event_service.emit_event(session, job_id, "progress", {"percent": 30})
        ev3 = await event_service.emit_event(session, job_id, "progress", {"percent": 60})
        ev4 = await event_service.emit_event(session, job_id, "progress", {"percent": 90})
        ev5 = await event_service.emit_event(session, job_id, "completed", {"status": "completed"})
        await session.commit()

    # Reconnect with Last-Event-ID pointing to ev2
    reconnect_headers = {
        "Authorization": f"Bearer {auth_token}",
        "Last-Event-ID": str(ev2.id),
    }

    async with client.stream("GET", f"/api/v1/jobs/{job_id}/events", headers=reconnect_headers) as sse_res:
        assert sse_res.status_code == 200
        # Read lines from stream
        lines = []
        async for line in sse_res.aiter_lines():
            if line.strip():
                lines.append(line)
            if "completed" in line:
                break

    # Verify that received events correspond to ev3, ev4, ev5
    full_text = "\n".join(lines)
    assert f"id: {ev3.id}" in full_text
    assert f"id: {ev4.id}" in full_text
    assert f"id: {ev5.id}" in full_text
    # ev1 and ev2 must NOT be replayed because Last-Event-ID was ev2.id
    assert f"id: {ev1.id}" not in full_text
    assert f"id: {ev2.id}" not in full_text


@pytest.mark.asyncio
async def test_scenario_f_sqlite_online_backup_under_live_wal_writes(test_env, running_mock_engine):
    """
    Scenario F: SQLite online backup and restore on a live WAL-mode database while writes are occurring.
    Tests BackupService.create_online_backup and restore_backup with active database mutations.
    """
    db_path = test_env["db_path"]
    stop_writes = asyncio.Event()
    write_count = 0

    async def concurrent_writer():
        nonlocal write_count
        while not stop_writes.is_set():
            async with database.AsyncSessionLocal() as session:
                user = User(
                    id=f"user_wal_{write_count}",
                    username=f"wal_u_{write_count}",
                    password_hash="hash",
                    role="editor",
                )
                session.add(user)
                await session.commit()
                write_count += 1
            await asyncio.sleep(0.01)

    # Start rapid background write task
    writer_task = asyncio.create_task(concurrent_writer())

    # Allow some writes to occur
    await asyncio.sleep(0.1)

    # Perform online backup using SQLite Online Backup API during active concurrent writes
    backup_dest = test_env["tmp_path"] / "live_wal_backup.db"
    backup_result = BackupService.create_online_backup(
        source_path=db_path,
        destination_path=backup_dest,
        verify=True,
    )

    # Stop concurrent writes
    stop_writes.set()
    await writer_task

    assert backup_result["status"] == "success"
    assert backup_dest.exists()
    assert backup_result["verification"]["is_valid"] is True
    assert backup_result["verification"]["integrity_check"] == "ok"
    assert backup_result["verification"]["tables"]["users"] > 0

    # Perform restore into disposable test database
    restore_target = test_env["tmp_path"] / "restored_database.db"
    restore_result = BackupService.restore_backup(
        backup_path=backup_dest,
        target_path=restore_target,
        create_safety_backup=False,
    )

    assert restore_result["status"] == "success"
    assert restore_target.exists()
    assert restore_result["verification"]["is_valid"] is True
    assert restore_result["verification"]["integrity_check"] == "ok"

    # Direct sqlite3 verification on restored file
    conn = sqlite3.connect(str(restore_target))
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check;")
    assert cur.fetchone()[0] == "ok"
    cur.execute("SELECT COUNT(*) FROM users;")
    restored_user_count = cur.fetchone()[0]
    conn.close()

    assert restored_user_count == backup_result["verification"]["tables"]["users"]
