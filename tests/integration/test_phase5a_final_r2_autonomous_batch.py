"""
Phase 5A Final Closure R2: Autonomous Progressive Batch Processing
Mandatory Scenario:
1. Create a disposable project with 100 short segments.
2. Submit the batch with the existing per-user outstanding limit of 25.
3. Stop all browser polling / project-status polling (NO GET /projects calls).
4. Allow the standalone runner / background daemon to process autonomously.
5. Verify pending segments are admitted into the queue as slots become available.
6. Verify no segment is lost or permanently stuck.
7. Simulate API process restart.
8. Simulate runner process restart separately.
9. Verify progress resumes correctly.
10. Verify the batch eventually completes with no duplicate authoritative audio artifacts.
"""

import asyncio
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.models.user import User
from apps.server.src.models.job import JobRecord
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.services.project_service import ProjectService, compute_segment_hash
from apps.server.src.services.durable_queue_service import DurableQueueService
from apps.server.src.services.resource_manager import resource_manager
from apps.server.src.supervisor.scheduler import DurableJobScheduler, scheduler
from apps.server.src.supervisor.supervisor import supervisor


@pytest.fixture(autouse=True)
async def cleanup_daemon():
    await scheduler.stop()
    await supervisor.stop_all()
    await resource_manager.reset()
    yield
    await scheduler.stop()
    await supervisor.stop_all()
    await resource_manager.reset()


@pytest.mark.asyncio
async def test_autonomous_progressive_batch_100_segments_no_browser_polling(test_env, running_mock_engine):
    """
    100-segment autonomous batch execution without browser polling.
    Verifies autonomous progressive admission, restart recovery, and artifact uniqueness.
    """
    await scheduler.stop()
    await resource_manager.reset()

    user_id = "user_batch_100"
    project_id = "proj_batch_100"

    # 1. Setup user and disposable project with 100 segments
    async with database.AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            username="batch_user_100",
            password_hash="h",
            role="editor",
            storage_quota_mb=500,
        )
        session.add(user)
        await session.flush()
        project = ProjectRecord(id=project_id, title="100 Segment Audiobook Chapter", user_id=user.id)
        session.add(project)
        await session.flush()

        for i in range(100):
            text = f"Đoạn văn ngắn số {i + 1} phục vụ kiểm thử autonomous batch."
            thash = compute_segment_hash(text, "mock-tts", "vi-female-1", {})
            seg = ScriptSegmentRecord(
                id=f"seg_100_{i:03d}",
                project_id=project.id,
                sequence_order=i + 1,
                text=text,
                language="vi",
                engine_id="mock-tts",
                voice_id="vi-female-1",
                status="draft",
                text_hash=thash,
                version=1,
            )
            session.add(seg)
        await session.commit()

        # 2. Submit the batch with per-user outstanding limit of 25
        rendered = await ProjectService.render_batch(session, user, project.id)
        assert len(rendered) == 100

        queued_initial = sum(1 for s, _ in rendered if s.status == "queued")
        pending_initial = sum(1 for s, _ in rendered if s.status == "pending")
        assert queued_initial == 25, f"Expected 25 queued initially, got {queued_initial}"
        assert pending_initial == 75, f"Expected 75 pending initially, got {pending_initial}"

    # 3. NO browser polling!
    # The client does NOT call ProjectService.get_project_record or GET /projects.
    # The background daemon alone must drive progressive admissions and execution.

    # 4. Start standalone runner / background daemon
    runner_daemon = DurableJobScheduler(poll_interval_seconds=0.05, lease_seconds=15)
    await runner_daemon.start()

    api_restarted = False
    runner_restarted = False
    timeout_seconds = 90.0
    start_time = asyncio.get_event_loop().time()

    # Monitor progress directly via read-only DB query (no project reconciliation API call)
    while True:
        await asyncio.sleep(0.1)
        async with database.AsyncSessionLocal() as s:
            completed_stmt = select(func.count(JobRecord.id)).where(
                JobRecord.user_id == user_id,
                JobRecord.status == "completed",
            )
            completed_jobs = (await s.execute(completed_stmt)).scalar() or 0

            seg_stmt = select(func.count(ScriptSegmentRecord.id)).where(
                ScriptSegmentRecord.project_id == project_id,
                ScriptSegmentRecord.status == "completed",
            )
            completed_segs_count = (await s.execute(seg_stmt)).scalar() or 0

        # 7. Step 35: Simulate API process restart (re-initialize connection pool)
        if completed_jobs >= 35 and not api_restarted:
            api_restarted = True
            await database.engine.dispose()

        # 8. Step 70: Simulate Runner process restart separately
        if completed_jobs >= 70 and not runner_restarted:
            runner_restarted = True
            await runner_daemon.stop()
            await asyncio.sleep(0.5)
            # Start fresh runner daemon
            runner_daemon = DurableJobScheduler(poll_interval_seconds=0.05, lease_seconds=15)
            await runner_daemon.start()

        if completed_jobs == 100 and completed_segs_count == 100:
            break

        if (asyncio.get_event_loop().time() - start_time) > timeout_seconds:
            await runner_daemon.stop()
            pytest.fail(f"Autonomous batch timed out. Completed jobs: {completed_jobs}/100, completed segments: {completed_segs_count}/100")

    await runner_daemon.stop()

    # Final reconciliation pass to update any remaining segment records
    await ProjectService.reconcile_and_admit_pending_segments()

    # 5, 6, 9, 10. Verification of the completed batch
    async with database.AsyncSessionLocal() as s:
        stmt = select(ScriptSegmentRecord).where(ScriptSegmentRecord.project_id == project_id)
        all_segs = (await s.execute(stmt)).scalars().all()

        assert len(all_segs) == 100, f"Expected 100 segments, got {len(all_segs)}"

        # Every segment must be completed
        completed_segs = [seg for seg in all_segs if seg.status == "completed"]
        assert len(completed_segs) == 100, f"Expected 100 completed, got {len(completed_segs)}"

        # No segment lost or permanently stuck
        pending_segs = [seg for seg in all_segs if seg.status == "pending"]
        assert len(pending_segs) == 0, f"Expected 0 pending, got {len(pending_segs)}"

        # Zero duplicate artifacts
        artifact_ids = [seg.active_artifact_id for seg in all_segs]
        assert len(set(artifact_ids)) == 100, "All 100 segments must have distinct, authoritative artifacts"
        assert None not in artifact_ids, "No segment can have None active_artifact_id"
