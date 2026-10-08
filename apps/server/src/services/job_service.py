"""
TTS Inference Job Queue & Execution Service (Facade over Durable Queue and Scheduler)
"""

from typing import List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import AppException
from ..models.job import JobRecord
from ..models.user import User
from ..schemas.job import TTSJobSubmitRequest
from .durable_queue_service import DurableQueueService
from ..supervisor.scheduler import scheduler


class JobService:
    @staticmethod
    async def submit_speech_job(
        db: AsyncSession,
        req: TTSJobSubmitRequest,
        current_user: User,
    ) -> JobRecord:
        job = await DurableQueueService.submit_speech_job(db, req, current_user)
        # Wake scheduler immediately for low latency dispatch
        scheduler.wake()
        return job

    @staticmethod
    async def get_job(
        db: AsyncSession,
        job_id: str,
        current_user: User,
    ) -> JobRecord:
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise AppException(
                status_code=404,
                title="Job Not Found",
                detail=f"Inference job '{job_id}' does not exist.",
                code="JOB_NOT_FOUND",
            )

        if job.user_id != current_user.id and current_user.role != "admin":
            raise AppException(
                status_code=403,
                title="Forbidden",
                detail="You do not have permission to view this job.",
                code="FORBIDDEN_JOB_ACCESS",
            )

        return job

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        current_user: User,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobRecord]:
        query = select(JobRecord)
        if current_user.role != "admin":
            query = query.where(JobRecord.user_id == current_user.id)
        query = query.order_by(desc(JobRecord.queued_at)).limit(limit).offset(offset)

        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def cancel_job(
        db: AsyncSession,
        job_id: str,
        current_user: User,
    ) -> JobRecord:
        return await DurableQueueService.cancel_job(job_id, current_user)

    @staticmethod
    async def retry_job(
        db: AsyncSession,
        job_id: str,
        current_user: User,
    ) -> JobRecord:
        job = await DurableQueueService.retry_failed_job(job_id, current_user)
        scheduler.wake()
        return job
