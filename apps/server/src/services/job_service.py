"""
TTS Inference Job Queue & Execution Service
"""

import asyncio
import base64
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import AppException
from ..models.engine import EngineRecord
from .. import database
from ..models.job import JobRecord
from ..models.user import User
from ..schemas.job import TTSJobSubmitRequest
from ..supervisor.supervisor import supervisor
from .artifact_service import ArtifactService
from engine_sdk.protocol import SynthesisRequest


class JobService:
    @staticmethod
    async def submit_speech_job(
        db: AsyncSession,
        req: TTSJobSubmitRequest,
        current_user: User,
    ) -> JobRecord:
        # 1. Idempotency Check
        if req.idempotency_key:
            stmt = select(JobRecord).where(
                JobRecord.user_id == current_user.id,
                JobRecord.idempotency_key == req.idempotency_key,
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

        # 2. Engine Registry Validation
        stmt = select(EngineRecord).where(EngineRecord.id == req.engine_id)
        res = await db.execute(stmt)
        engine_rec = res.scalar_one_or_none()
        if not engine_rec:
            raise AppException(
                status_code=400,
                title="Engine Not Found",
                detail=f"Engine '{req.engine_id}' is not installed or registered.",
                code="ENGINE_NOT_FOUND",
            )

        # 3. Worker Client Availability Check
        client = supervisor.get_client(req.engine_id)
        if not client:
            raise AppException(
                status_code=503,
                title="Engine Unavailable",
                detail=f"Worker process for engine '{req.engine_id}' is not running.",
                code="ENGINE_UNAVAILABLE",
            )

        # 4. Language Capability Validation
        manifest_dict = engine_rec.manifest_data or {}
        supported_langs = manifest_dict.get("supported_languages", ["vi"])
        if req.language not in supported_langs:
            raise AppException(
                status_code=422,
                title="Unsupported Language",
                detail=f"Engine '{req.engine_id}' does not support language '{req.language}'. Supported: {supported_langs}",
                code="UNSUPPORTED_LANGUAGE",
            )

        # 5. Create Job Record in SQLite WAL
        job_id = str(uuid.uuid4())
        job = JobRecord(
            id=job_id,
            user_id=current_user.id,
            engine_id=req.engine_id,
            idempotency_key=req.idempotency_key,
            job_type="tts",
            status="queued",
            progress_percent=0,
            payload_data=req.model_dump(),
            queued_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # 6. Dispatch Async Execution
        asyncio.create_task(JobService.execute_job(job_id))

        return job

    @staticmethod
    async def execute_job(job_id: str):
        """
        Background execution task for a queued TTS job.
        Uses a fresh AsyncSession to avoid lifetime binding issues.
        """
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                return

            job.status = "running"
            job.progress_percent = 20
            job.started_at = datetime.now(timezone.utc)
            await session.commit()

            try:
                client = supervisor.get_client(job.engine_id)
                if not client:
                    raise RuntimeError(f"Engine worker for '{job.engine_id}' is not reachable.")

                payload = job.payload_data or {}
                synthesis_req = SynthesisRequest(
                    job_id=job.id,
                    text=payload.get("text", ""),
                    language=payload.get("language", "vi"),
                    voice_id=payload.get("voice_id"),
                    speed=float(payload.get("speed", 1.0)),
                    output_format="wav",
                )

                job.progress_percent = 50
                await session.commit()

                audio_bytes = await client.synthesize(synthesis_req)

                job.progress_percent = 80
                await session.commit()

                # Persist audio artifact
                artifact = await ArtifactService.create_artifact_from_bytes(
                    db=session,
                    owner_id=job.user_id,
                    audio_bytes=audio_bytes,
                    format="wav",
                )

                # Finalize job
                job.status = "completed"
                job.progress_percent = 100
                job.artifact_id = artifact.id
                job.finished_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as exc:
                job.status = "failed"
                job.error_details = {
                    "code": getattr(exc, "code", "SYNTHESIS_FAILED"),
                    "message": str(exc),
                }
                job.finished_at = datetime.now(timezone.utc)
                await session.commit()

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
        job = await JobService.get_job(db, job_id, current_user)
        if job.status in ("completed", "failed", "cancelled"):
            return job

        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        return job
