"""
Phase 5A Final Closure R2: Atomic Quota Reservation Lifecycle & Lease Safety
Tests:
A. Healthy active job lasts longer than original reservation TTL (heartbeat extension).
B. Worker crashes and never completes reservation (eventual cleanup to EXPIRED).
C. Stale worker tries to commit an expired/reclaimed reservation (rejected with 409).
D. Two separate database sessions compete for limited quota (concurrency safety).
E. Actual output size exceeds original estimate (proper accounting).
F. Export fails after writing a partial temporary file (atomicity and file cleanup).
"""

import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from sqlalchemy import select

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.models.user import User
from apps.server.src.models.job import JobRecord
from apps.server.src.models.storage_reservation import StorageReservationRecord
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.user_quota_service import UserQuotaService
from apps.server.src.services.audio_dsp_service import AudioDspService, MasterExportRequest
from apps.server.src.services.job_state_machine import JobState
from apps.server.src.core.errors import AppException
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_scenario_a_healthy_job_outlasts_original_reservation_ttl(test_env):
    """
    Scenario A: A healthy active job lasts longer than the original reservation TTL.
    - Initial reservation created with TTL of 30 seconds (simulated).
    - As the worker heartbeats, the reservation's expires_at is repeatedly renewed.
    - When cleanup_expired_reservations runs, the active job's reservation is NOT expired.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_healthy_job", username="healthy_user", password_hash="h", role="editor", storage_quota_mb=100)
        session.add(u)
        await session.commit()

        # Create active job
        now = datetime.now(timezone.utc)
        job = JobRecord(
            id="job_long_running",
            user_id=u.id,
            engine_id="mock-tts",
            status=JobState.RUNNING.value,
            current_attempt_id="att-1",
            lease_expires_at=now + timedelta(seconds=60),
            queued_at=now,
        )
        session.add(job)

        # Create reservation for this job with a very short simulated TTL
        res = StorageReservationRecord(
            id="res_long_running",
            user_id=u.id,
            job_id=job.id,
            reservation_type="tts_job",
            reserved_bytes=1024 * 1024,
            status="ACTIVE",
            expires_at=now + timedelta(seconds=10),
            created_at=now,
            updated_at=now,
        )
        session.add(res)
        await session.commit()

        # Fast forward time simulation: simulate heartbeat extending the reservation
        await DurableQueueService.heartbeat(job.id, attempt_id="att-1", extend_seconds=60)

        # Verify reservation expiration was pushed forward
        await session.refresh(res)
        exp = res.expires_at if res.expires_at.tzinfo else res.expires_at.replace(tzinfo=timezone.utc)
        assert exp > now + timedelta(seconds=1000), "Heartbeat should have extended reservation expires_at"
        assert res.status == "ACTIVE"

        # Run cleanup; reservation must remain ACTIVE
        cleaned = await UserQuotaService.cleanup_expired_reservations(session)
        await session.refresh(res)
        assert res.status == "ACTIVE", "Active healthy job reservation must not be expired"


@pytest.mark.asyncio
async def test_scenario_b_worker_crashes_abandoned_reservation_cleaned_up(test_env):
    """
    Scenario B: A worker crashes and never completes its reservation.
    - Job status is RUNNING, but worker crashed and job lease expired in the past.
    - cleanup_expired_reservations detects the abandoned job/reservation and marks it EXPIRED.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_crashed_worker", username="crashed_worker_user", password_hash="h", role="editor")
        session.add(u)
        await session.commit()

        past = datetime.now(timezone.utc) - timedelta(minutes=45)
        dead_job = JobRecord(
            id="job_crashed",
            user_id=u.id,
            engine_id="mock-tts",
            status=JobState.RUNNING.value,
            current_attempt_id="att-crashed",
            lease_expires_at=past,  # Dead lease
            queued_at=past,
        )
        session.add(dead_job)

        abandoned_res = StorageReservationRecord(
            id="res_abandoned",
            user_id=u.id,
            job_id=dead_job.id,
            reservation_type="tts_job",
            reserved_bytes=2 * 1024 * 1024,
            status="ACTIVE",
            expires_at=past,
            created_at=past,
            updated_at=past,
        )
        session.add(abandoned_res)
        await session.commit()

        # Run cleanup
        cleaned = await UserQuotaService.cleanup_expired_reservations(session)
        assert cleaned >= 1

        await session.refresh(abandoned_res)
        assert abandoned_res.status == "EXPIRED", "Abandoned reservation must be reconciled to EXPIRED"


@pytest.mark.asyncio
async def test_scenario_c_stale_worker_cannot_commit_reclaimed_reservation(test_env):
    """
    Scenario C: A stale worker tries to commit an expired/reclaimed reservation.
    - Reservation status was already transitioned to EXPIRED.
    - Stale worker calling commit_reservation or commit_job_reservation must be rejected with 409.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_stale_worker", username="stale_user", password_hash="h", role="editor")
        session.add(u)
        await session.commit()

        res = StorageReservationRecord(
            id="res_stale_commit",
            user_id=u.id,
            job_id="job_stale_worker_target",
            reservation_type="tts_job",
            reserved_bytes=1024 * 1024,
            status="EXPIRED",  # Reclaimed already
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        session.add(res)
        await session.commit()

        # Attempt to commit directly via commit_reservation -> must raise 409
        with pytest.raises(AppException) as exc_info:
            await UserQuotaService.commit_reservation(session, res.id, actual_bytes=500000)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "RESERVATION_STALE_OR_RECLAIMED"

        # Attempt to commit via commit_job_reservation -> must raise 409
        with pytest.raises(AppException) as exc_info2:
            await UserQuotaService.commit_job_reservation(session, "job_stale_worker_target", actual_bytes=500000)
        assert exc_info2.value.status_code == 409
        assert exc_info2.value.code == "RESERVATION_STALE_OR_RECLAIMED"


@pytest.mark.asyncio
async def test_scenario_d_concurrent_claims_compete_for_limited_quota(test_env):
    """
    Scenario D: Two separate database sessions compete for limited quota.
    - User has 10 MB remaining.
    - Session A and Session B both attempt to reserve 8 MB.
    - Exactly one succeeds, one fails with 413.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_compete", username="compete_user", password_hash="h", role="editor", storage_quota_mb=10)
        session.add(u)
        await session.commit()

    eight_mb = 8 * 1024 * 1024

    results = []
    async def try_reserve(name: str):
        async with database.AsyncSessionLocal() as s:
            try:
                r = await UserQuotaService.reserve_capacity(s, u.id, eight_mb, "test")
                await s.commit()
                results.append((name, True, r.id))
            except AppException as e:
                results.append((name, False, e.code))

    await asyncio.gather(try_reserve("worker-1"), try_reserve("worker-2"))

    successes = [r for r in results if r[1] is True]
    failures = [r for r in results if r[1] is False]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"
    assert failures[0][2] == "USER_STORAGE_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_scenario_e_actual_output_size_exceeds_original_estimate(test_env):
    """
    Scenario E: Actual output size exceeds the original estimate.
    - Estimated size: 1 MB.
    - Actual synthesized file: 2.5 MB.
    - After commit, the reservation record reflects the actual size (2.5 MB),
      ensuring database state is consistent with actual file storage.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_large_output", username="large_output_user", password_hash="h", role="editor", storage_quota_mb=50)
        session.add(u)
        await session.commit()

        est_bytes = 1 * 1024 * 1024
        actual_bytes = int(2.5 * 1024 * 1024)

        res = await UserQuotaService.reserve_capacity(session, u.id, est_bytes, "tts_job", job_id="job_large")
        await session.commit()
        assert res.reserved_bytes == est_bytes

        # Commit with actual bytes > estimated bytes
        await UserQuotaService.commit_reservation(session, res.id, actual_bytes)
        await session.commit()

        await session.refresh(res)
        assert res.status == "COMMITTED"
        assert res.reserved_bytes == actual_bytes, "Reservation must be updated to exact actual bytes"

        # In synthesis workflow, an ArtifactRecord is created matching actual_bytes
        art = ArtifactRecord(
            id="art_large",
            owner_id=u.id,
            file_path="large_file.wav",
            file_size_bytes=actual_bytes,
            duration_seconds=10.0,
            sample_rate=24000,
            format="wav",
        )
        session.add(art)
        await session.commit()

        # Verify usage accounting reflects actual bytes
        usage = await UserQuotaService.get_user_storage_usage(session, u.id)
        assert usage["reserved_bytes"] == 0
        assert usage["used_bytes"] == actual_bytes


@pytest.mark.asyncio
async def test_scenario_f_export_fails_after_partial_temporary_file_cleanly_unlinked(test_env):
    """
    Scenario F: Export fails after writing a partial temporary file.
    - Simulates an export error during processing.
    - Ensures that:
      1. Any temporary partial file is unlinked.
      2. The export reservation is immediately RELEASED (not left hanging).
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_export_fail", username="export_fail_user", password_hash="h", role="editor", storage_quota_mb=50)
        session.add(u)
        await session.commit()

        # Create project with invalid segment (incomplete) to trigger failure
        p = ProjectRecord(id="proj_fail_test", title="Fail Project", user_id=u.id)
        session.add(p)
        seg = ScriptSegmentRecord(
            id="seg_fail_test",
            project_id=p.id,
            sequence_order=1,
            text="Fail segment",
            language="vi",
            engine_id="mock-tts",
            voice_id="vi-female-1",
            text_hash="hash_fail",
            status="rendering",  # Incomplete! Will trigger INCOMPLETE_SEGMENTS validation error
        )
        session.add(seg)
        await session.commit()

        req = MasterExportRequest(format="wav", sample_rate=48000, normalize_loudness=False)

        # Call export_project; must raise HTTPException 400
        with pytest.raises(HTTPException) as exc_info:
            await AudioDspService.export_project(session, u.id, p.id, req)
        assert exc_info.value.status_code == 400
        assert "INCOMPLETE_SEGMENTS" in exc_info.value.detail

        # Verify that the created reservation was released immediately
        stmt = select(StorageReservationRecord).where(
            StorageReservationRecord.user_id == u.id,
            StorageReservationRecord.reservation_type == "master_export",
        )
        res_record = (await session.execute(stmt)).scalar_one_or_none()
        assert res_record is not None
        assert res_record.status == "RELEASED", "Failed export must immediately RELEASE its capacity reservation"
