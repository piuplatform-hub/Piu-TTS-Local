"""
TTS Inference Jobs API Endpoints (v1)
Includes Durable Queue submission, SSE event streaming, cancellation, and manual retry.
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...models.job import JobRecord
from ...schemas.job import TTSJobSubmitRequest, JobResponse
from ...services.auth_service import get_current_user, get_user_from_token_str
from ...services.job_service import JobService
from ...services.event_service import event_service
from ...core.errors import AppException

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _to_job_response(rec: JobRecord) -> JobResponse:
    return JobResponse(
        id=rec.id,
        user_id=rec.user_id,
        engine_id=rec.engine_id,
        job_type=rec.job_type,
        status=rec.status,
        progress_percent=rec.progress_percent,
        priority=rec.priority,
        resource_type=rec.resource_type,
        attempt_count=rec.attempt_count,
        max_retries=rec.max_retries,
        waiting_reason=rec.waiting_reason,
        artifact_id=rec.artifact_id,
        error_details=rec.error_details,
        queued_at=rec.queued_at,
        started_at=rec.started_at,
        finished_at=rec.finished_at,
    )


@router.post("/speech", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_speech_job(
    req: TTSJobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submits a Text-to-Speech synthesis job into the durable SQLite queue.
    Enforces idempotency and payload collision checks (409 Conflict).
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


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually retries a failed job, resetting attempts and re-enqueueing.
    """
    job = await JobService.retry_job(db, job_id, current_user)
    return _to_job_response(job)


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    token: Optional[str] = Query(None),
    last_event_id: Optional[int] = Query(None),
    last_event_id_header: Optional[int] = Header(None, alias="Last-Event-ID"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events (SSE) streaming endpoint for live job status and progress.
    Supports query parameter authentication for browser EventSource API
    and Last-Event-ID replay for disconnected clients.
    """
    # 1. Resolve Auth Token
    token_str: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token_str = authorization[7:].strip()
    elif token:
        token_str = token.strip()

    if not token_str:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Authentication Required",
            detail="Missing Bearer token in Authorization header or 'token' query parameter.",
            code="UNAUTHORIZED",
        )

    # 2. Authenticate User
    current_user = await get_user_from_token_str(token_str, db)

    # 3. Check Job Access
    await JobService.get_job(db, job_id, current_user)

    effective_last_event_id = last_event_id if last_event_id is not None else last_event_id_header

    # 4. SSE Stream Generator
    async def sse_generator():
        async for event in event_service.subscribe(job_id, effective_last_event_id):
            eid = event.get("id")
            etype = event.get("event_type", "message")
            edata = json.dumps(event.get("data", {}))
            if eid is not None:
                yield f"id: {eid}\nevent: {etype}\ndata: {edata}\n\n"
            else:
                yield f"event: {etype}\ndata: {edata}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
