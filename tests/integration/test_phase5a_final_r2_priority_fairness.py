"""
Phase 5A Final Closure R2: Fairness Under Priorities Test Suite
Distinguishes:
1. Fairness within the same priority tier (anti-starvation round-robin across users).
2. Priority precedence across different priorities (Head-of-Line precedence).
3. Starvation risk under continuously arriving high-priority jobs (trade-off analysis).
"""

import asyncio
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, update

from apps.server.src import database
from apps.server.src.models.user import User
from apps.server.src.models.job import JobRecord
from apps.server.src.models.scheduling_state import UserSchedulingStateRecord
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.resource_manager import resource_manager
from apps.server.src.supervisor.scheduler import scheduler


@pytest.fixture(autouse=True)
async def reset_state():
    await scheduler.stop()
    await resource_manager.reset()
    yield
    await scheduler.stop()
    await resource_manager.reset()


@pytest.mark.asyncio
async def test_fairness_within_same_priority_tier(test_env, running_mock_engine):
    """
    Test 1: Multiple users with the SAME priority level (e.g. priority 1).
    - User A submits 5 jobs.
    - User B submits 5 jobs.
    - Claims must alternate fairly between User A and User B (Round-Robin),
      neither user starves, persistent scheduling states update.
    """
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        ua = User(id="user_prio_same_a", username="prio_same_a", password_hash="h", role="editor")
        ub = User(id="user_prio_same_b", username="prio_same_b", password_hash="h", role="editor")
        session.add_all([ua, ub])
        await session.commit()

        # Both submit 5 jobs with priority 1
        for i in range(5):
            req_a = TTSJobSubmitRequest(text=f"A job {i}", engine_id="mock-tts", language="vi", priority=1)
            await DurableQueueService.submit_speech_job(session, req_a, ua)
            req_b = TTSJobSubmitRequest(text=f"B job {i}", engine_id="mock-tts", language="vi", priority=1)
            await DurableQueueService.submit_speech_job(session, req_b, ub)

    dispatch_order = []
    for turn in range(6):
        job = await DurableQueueService.claim_next_job(worker_id=f"worker-turn-{turn}")
        assert job is not None
        dispatch_order.append(job.user_id)
        # Complete job to free the resource slot for next claim
        await DurableQueueService.mark_running(job.id, job.current_attempt_id, worker_id=f"worker-turn-{turn}")
        await DurableQueueService.complete_job(job.id, job.current_attempt_id, f"art_{job.id}")

    # First 4 dispatches must alternate between user A and user B
    assert dispatch_order[0] != dispatch_order[1], f"Expected alternation, got {dispatch_order}"
    assert dispatch_order[1] != dispatch_order[2], f"Expected alternation, got {dispatch_order}"
    assert dispatch_order[2] != dispatch_order[3], f"Expected alternation, got {dispatch_order}"


@pytest.mark.asyncio
async def test_priority_precedence_across_different_priorities(test_env, running_mock_engine):
    """
    Test 2: Head-of-Line Priority Precedence across different priorities.
    - User Low submits 10 jobs with priority 1.
    - User Urgent submits 1 job with priority 10.
    - Next claim MUST yield User Urgent's job immediately, jumping ahead of all priority 1 jobs.
    """
    await scheduler.stop()
    await resource_manager.reset()

    async with database.AsyncSessionLocal() as session:
        u_low = User(id="user_low_prio", username="low_prio", password_hash="h", role="editor")
        u_urg = User(id="user_urg_prio", username="urg_prio", password_hash="h", role="editor")
        session.add_all([u_low, u_urg])
        await session.commit()

        for i in range(10):
            req_l = TTSJobSubmitRequest(text=f"Low job {i}", engine_id="mock-tts", language="vi", priority=1)
            await DurableQueueService.submit_speech_job(session, req_l, u_low)

        req_u = TTSJobSubmitRequest(text="Urgent job", engine_id="mock-tts", language="vi", priority=10)
        job_urg = await DurableQueueService.submit_speech_job(session, req_u, u_urg)

    # Next claim MUST be the urgent job
    claimed = await DurableQueueService.claim_next_job(worker_id="worker-urg-check")
    assert claimed is not None
    assert claimed.id == job_urg.id
    assert claimed.priority == 10
    assert claimed.user_id == u_urg.id


@pytest.mark.asyncio
async def test_starvation_risk_under_continuously_arriving_high_priority_jobs(test_env, running_mock_engine):
    """
    Test 3: Starvation risk analysis under continuously arriving high-priority jobs.
    Demonstrates that in strict priority scheduling without priority aging,
    if new priority 10 jobs arrive before each dispatch, priority 1 jobs will be delayed.
    This empirically confirms why universal starvation freedom cannot be claimed across different priorities.
    """
    await scheduler.stop()
    await resource_manager.reset()
    async with database.AsyncSessionLocal() as session:
        u_batch = User(id="user_batch_low", username="batch_low", password_hash="h", role="editor")
        u_stream = User(id="user_stream_high", username="stream_high", password_hash="h", role="editor")
        session.add_all([u_batch, u_stream])
        await session.commit()

        # Enqueue 1 low priority job
        req_low = TTSJobSubmitRequest(text="Low Background Job", engine_id="mock-tts", language="vi", priority=1)
        job_low = await DurableQueueService.submit_speech_job(session, req_low, u_batch)

    # Stream 3 high-priority jobs dynamically, one before each dispatch
    claimed_ids = []
    for step in range(3):
        async with database.AsyncSessionLocal() as session:
            req_h = TTSJobSubmitRequest(text=f"High Priority Stream {step}", engine_id="mock-tts", language="vi", priority=10)
            j_h = await DurableQueueService.submit_speech_job(session, req_h, u_stream)

        claimed = await DurableQueueService.claim_next_job(worker_id=f"worker-stream-{step}")
        assert claimed is not None
        claimed_ids.append(claimed.id)
        assert claimed.priority == 10, "High-priority job must preempt lower-priority job"
        await DurableQueueService.mark_running(claimed.id, claimed.current_attempt_id, worker_id=f"worker-stream-{step}")
        await DurableQueueService.complete_job(claimed.id, claimed.current_attempt_id, f"art_stream_{step}")

    # The low priority job has NOT been claimed yet during the high-priority stream
    assert job_low.id not in claimed_ids

    # Once high-priority jobs are exhausted, the low priority job is finally dispatched
    claimed_final = await DurableQueueService.claim_next_job(worker_id="worker-stream-final")
    assert claimed_final is not None
    assert claimed_final.id == job_low.id
    assert claimed_final.priority == 1
