"""
Independent Durable Job Scheduler Daemon
Continuously claims eligible jobs, enforces concurrency slots, drives worker execution,
and monitors heartbeat/lease expirations. Runs inside FastAPI lifespan.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
from typing import Dict, Optional, Set

from engine_sdk.protocol import SynthesisRequest

from .. import database
from ..models.job import JobRecord
from ..services.artifact_service import ArtifactService
from ..services.durable_queue_service import DurableQueueService, FencingTokenError
from ..services.job_state_machine import JobState
from ..services.resource_manager import resource_manager
from .supervisor import supervisor

logger = logging.getLogger("studio.scheduler")


class DurableJobScheduler:
    def __init__(
        self,
        poll_interval_seconds: float = 0.5,
        lease_seconds: int = 30,
        worker_id: Optional[str] = None,
    ):
        self.poll_interval = poll_interval_seconds
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or f"scheduler-{os.getpid()}"
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._active_tasks: Set[asyncio.Task] = set()
        self._wake_event = asyncio.Event()

    def wake(self):
        """Notifies scheduler to immediately check queue without waiting for poll interval."""
        self._wake_event.set()

    async def start(self):
        """Starts the scheduler daemon and performs startup crash recovery."""
        if self._running:
            return
        self._running = True
        self._wake_event = asyncio.Event()

        # Perform crash & restart recovery for stranded jobs
        recovered = await DurableQueueService.recover_on_startup()
        if recovered > 0:
            logger.warning(f"DurableJobScheduler: Recovered {recovered} stranded jobs on startup.")

        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("DurableJobScheduler started successfully.")

    async def stop(self):
        """Gracefully shuts down scheduler and waits for active job tasks to finish or terminate."""
        if not self._running:
            return
        self._running = False
        self.wake()

        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        # Wait briefly for active tasks
        if self._active_tasks:
            done, pending = await asyncio.wait(self._active_tasks, timeout=3.0)
            for t in pending:
                t.cancel()

        self._active_tasks.clear()
        logger.info("DurableJobScheduler stopped cleanly.")

    async def _run_loop(self):
        while self._running:
            try:
                # 1. Reclaim any expired leases
                await DurableQueueService.reclaim_expired_leases()

                # 2. Attempt to claim next ready job
                claimed_job = await DurableQueueService.claim_next_job(
                    worker_id=self.worker_id,
                    lease_duration_seconds=self.lease_seconds,
                )

                if claimed_job:
                    # Spawn worker execution task
                    task = asyncio.create_task(self._execute_job(claimed_job))
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
                    # Loop immediately to check if another eligible job can run in parallel
                    continue

                # 3. Wait for wake signal or polling interval
                try:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=self.poll_interval)
                    self._wake_event.clear()
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in scheduler loop: {exc}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _execute_job(self, job: JobRecord):
        """
        Executes synthesis workflow for a claimed job in an independent task.
        Runs background heartbeats to refresh lease.
        """
        job_id = job.id
        attempt_id = job.current_attempt_id
        if not attempt_id:
            logger.error(f"Job {job_id} missing attempt_id. Aborting execution.")
            return

        stop_heartbeat = asyncio.Event()

        # Background heartbeat runner
        async def heartbeat_worker():
            while not stop_heartbeat.is_set():
                try:
                    await asyncio.wait_for(stop_heartbeat.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    renewed = await DurableQueueService.heartbeat(
                        job_id=job_id,
                        attempt_id=attempt_id,
                        extend_seconds=self.lease_seconds,
                    )
                    if not renewed:
                        # Lease was revoked or fencing token became stale
                        break

        hb_task = asyncio.create_task(heartbeat_worker())

        try:
            # 1. Transition to running
            await DurableQueueService.mark_running(
                job_id=job_id,
                attempt_id=attempt_id,
                worker_id=self.worker_id,
            )

            # 2. Fetch worker client
            client = supervisor.get_client(job.engine_id)
            if not client:
                raise RuntimeError(f"Engine worker for '{job.engine_id}' is not reachable.")

            # Update progress percent to 30%
            await DurableQueueService.heartbeat(
                job_id=job_id,
                attempt_id=attempt_id,
                extend_seconds=self.lease_seconds,
                progress_percent=30,
            )

            # 3. Synthesis request to isolated worker
            payload = job.payload_data or {}
            synthesis_req = SynthesisRequest(
                job_id=job.id,
                text=payload.get("text", ""),
                language=payload.get("language", "vi"),
                voice_id=payload.get("voice_id"),
                speed=float(payload.get("speed", 1.0)),
                output_format="wav",
            )

            # Update progress percent to 60%
            await DurableQueueService.heartbeat(
                job_id=job_id,
                attempt_id=attempt_id,
                extend_seconds=self.lease_seconds,
                progress_percent=60,
            )

            audio_bytes = await client.synthesize(synthesis_req)

            # Update progress percent to 90%
            await DurableQueueService.heartbeat(
                job_id=job_id,
                attempt_id=attempt_id,
                extend_seconds=self.lease_seconds,
                progress_percent=90,
            )

            # 4. Save audio artifact
            async with database.AsyncSessionLocal() as session:
                artifact = await ArtifactService.create_artifact_from_bytes(
                    db=session,
                    owner_id=job.user_id,
                    audio_bytes=audio_bytes,
                    format="wav",
                )

            # 5. Commit completion with fencing token
            await DurableQueueService.complete_job(
                job_id=job_id,
                attempt_id=attempt_id,
                artifact_id=artifact.id,
            )

        except FencingTokenError as fe:
            logger.warning(f"Fencing token rejected completion for job {job_id}: {fe}")
        except Exception as exc:
            if not self._running:
                return
            logger.error(f"Job {job_id} failed with error: {exc}")
            retryable = not isinstance(exc, (ValueError, TypeError))
            await DurableQueueService.fail_job(
                job_id=job_id,
                attempt_id=attempt_id,
                error_code=getattr(exc, "code", "SYNTHESIS_FAILED"),
                error_message=str(exc),
                retryable=retryable,
            )
        finally:
            stop_heartbeat.set()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass


# Global singleton instance
scheduler = DurableJobScheduler()
