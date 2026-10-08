"""
TTS Inference Jobs API Endpoints (v1)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...models.job import JobRecord
from ...schemas.job import TTSJobSubmitRequest, JobResponse
from ...services.auth_service import get_current_user
from ...services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _to_job_response(rec: JobRecord) -> JobResponse:
    return JobResponse(
        id=rec.id,
        user_id=rec.user_id,
        engine_id=rec.engine_id,
        job_type=rec.job_type,
        status=rec.status,
        progress_percent=rec.progress_percent,
        artifact_id=rec.artifact_id,
        error_details=rec.error_details,
        queued_at=rec.queued_at,
        finished_at=rec.finished_at,
    )


@router.post("/speech", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_speech_job(
    req: TTSJobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submits a Text-to-Speech synthesis job.
    Supports client idempotency key to prevent duplicate runs.
    """
    job = await JobService.submit_speech_job(db, req, current_user)
    return _to_job_response(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Poll or inspect the status, progress, and artifact link of a specific job.
    """
    job = await JobService.get_job(db, job_id, current_user)
    return _to_job_response(job)


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List recent jobs belonging to the current user (or all jobs if admin).
    """
    jobs = await JobService.list_jobs(db, current_user, limit=limit, offset=offset)
    return [_to_job_response(j) for j in jobs]


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a queued or active job.
    """
    job = await JobService.cancel_job(db, job_id, current_user)
    return _to_job_response(job)
