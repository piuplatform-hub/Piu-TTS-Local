"""
Durable Queue Service (SQLite Transactional Queue with Fencing Tokens and Lease Recovery)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import uuid

from sqlalchemy import select, update, desc, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import database
from ..config import settings
from ..core.errors import AppException
from ..models.asset import ReferenceAssetRecord
from ..models.engine import EngineRecord
from ..models.job import JobRecord
from ..models.user import User
from ..models.scheduling_state import UserSchedulingStateRecord
from ..schemas.job import TTSJobSubmitRequest
from .event_service import event_service
from .job_state_machine import JobStateMachine, JobState
from .resource_manager import resource_manager
from .user_quota_service import UserQuotaService


class FencingTokenError(AppException):
    def __init__(self, job_id: str, attempt_id: str, expected_id: Optional[str]):
        super().__init__(
            status_code=409,
            title="Fencing Token Mismatch",
            detail=f"Completion rejected for job '{job_id}'. Stale attempt '{attempt_id}' vs current attempt '{expected_id}'.",
            code="FENCING_TOKEN_MISMATCH",
        )


class DurableQueueService:
    @staticmethod
    async def _validate_and_sanitize_request(
        db: AsyncSession,
        engine_rec: EngineRecord,
        req: TTSJobSubmitRequest,
        current_user: User,
    ) -> Dict[str, Any]:
        manifest_dict = engine_rec.manifest_data or {}
        capabilities = engine_rec.capabilities or []

        # A. Language Validation
        supported_langs = manifest_dict.get("supported_languages", ["vi"])
        if req.language not in supported_langs:
            raise AppException(
                status_code=422,
                title="Unsupported Language",
                detail=f"Engine '{req.engine_id}' does not support language '{req.language}'. Supported: {supported_langs}",
                code="UNSUPPORTED_LANGUAGE",
            )

        # B. Voice Selection Validation
        if req.voice_id:
            valid_voices = set()
            if req.engine_id == "vieneu-tts":
                valid_voices = {
                    "hai_dang", "mai_anh", "truc_ly", "thien_minh", "thuy_dung",
                    "thien_tam_duc", "ngoc_huyen", "quang_son", "ngoc_tran", "minh_duc",
                    "thai_son", "xuan_vinh", "ngoc_linh", "doan_trang", "thuc_doan",
                    "minh_triet", "my_duyen", "quynh_anh", "duc_tri", "kim_thanh",
                    "adam", "quoc_tuan"
                }
            elif req.engine_id == "qwen3-tts":
                valid_voices = {
                    "vivian", "uncle_fu", "serena", "aiden", "dylan",
                    "eric", "ono_anna", "ryan", "sohee"
                }
            elif req.engine_id == "mock-tts":
                valid_voices = {"vi-female-1", "vi-male-1", "en-female-1", "zh-female-1"}

            if valid_voices and req.voice_id.lower() not in valid_voices:
                raise AppException(
                    status_code=422,
                    title="Unsupported Voice",
                    detail=f"Voice '{req.voice_id}' is not supported by engine '{req.engine_id}'. Valid voices: {sorted(list(valid_voices))}",
                    code="UNSUPPORTED_VOICE",
                )

        # C. Parameters Schema & Capabilities Validation
        params_schema = manifest_dict.get("parameters_schema", {})
        input_params = dict(req.parameters or {})
        sanitized_params = {}

        # 1. Check for Voice Cloning request and capability
        has_cloning = "reference_asset_id" in input_params or "ref_audio" in input_params
        if has_cloning:
            if "voice_cloning" not in capabilities:
                raise AppException(
                    status_code=422,
                    title="Voice Cloning Not Supported",
                    detail=f"Engine '{req.engine_id}' does not support voice cloning capabilities.",
                    code="VOICE_CLONING_NOT_SUPPORTED",
                )

            # Prevent direct client-supplied host filesystem paths (Path Traversal / Host Injection)
            raw_ref = input_params.get("ref_audio")
            raw_asset_id = input_params.get("reference_asset_id")

            if raw_ref and any(c in str(raw_ref) for c in ("/", "\\", "..", ":")):
                raise AppException(
                    status_code=422,
                    title="Filesystem Path Injection Prohibited",
                    detail="Arbitrary client-supplied filesystem paths are prohibited. You must upload the audio reference via /api/v1/assets/reference-audio and provide reference_asset_id.",
                    code="FILESYSTEM_PATH_INJECTION_PROHIBITED",
                )

            effective_asset_id = raw_asset_id or raw_ref
            if not effective_asset_id:
                raise AppException(
                    status_code=422,
                    title="Missing Reference Asset",
                    detail="Voice cloning requires a valid reference_asset_id.",
                    code="MISSING_REFERENCE_ASSET",
                )

            # Query ReferenceAssetRecord from DB
            asset_stmt = select(ReferenceAssetRecord).where(ReferenceAssetRecord.id == str(effective_asset_id))
            asset_res = await db.execute(asset_stmt)
            asset_rec = asset_res.scalar_one_or_none()

            if not asset_rec:
                raise AppException(
                    status_code=404,
                    title="Reference Asset Not Found",
                    detail=f"Reference audio asset '{effective_asset_id}' does not exist.",
                    code="REFERENCE_ASSET_NOT_FOUND",
                )

            # Strict per-user ownership check (Disallow admin silent bypass for private voice references)
            if asset_rec.user_id != current_user.id:
                raise AppException(
                    status_code=403,
                    title="Access Denied",
                    detail="You do not have authorization to access or use this reference audio asset.",
                    code="FORBIDDEN_ASSET_ACCESS",
                )

            # Explicit consent check
            if not asset_rec.voice_use_consent:
                raise AppException(
                    status_code=400,
                    title="Voice Use Consent Required",
                    detail="The referenced audio sample lacks verified voice-use consent.",
                    code="VOICE_CONSENT_REQUIRED",
                )

            # Resolve to verified safe server path for the isolated worker
            sanitized_params["ref_audio"] = asset_rec.file_path
            sanitized_params["reference_asset_id"] = asset_rec.id

        # 2. Allowed parameter keys for this engine
        allowed_keys = set(params_schema.keys())
        if "voice_cloning" in capabilities:
            allowed_keys.add("reference_asset_id")

        for key in input_params.keys():
            if key not in allowed_keys:
                raise AppException(
                    status_code=422,
                    title="Unsupported Parameter",
                    detail=f"Parameter '{key}' is not recognized or supported by engine '{req.engine_id}'. Allowed: {sorted(list(allowed_keys))}",
                    code="UNSUPPORTED_PARAMETER",
                )

        # D. Validate other parameters
        if "speed" in input_params:
            speed_val = input_params["speed"]
            if not isinstance(speed_val, (int, float)) or not (0.25 <= float(speed_val) <= 4.0):
                raise AppException(
                    status_code=422,
                    title="Invalid Speed",
                    detail=f"Speed parameter must be a number between 0.25 and 4.0, received: {speed_val}",
                    code="INVALID_PARAMETER_VALUE",
                )
            sanitized_params["speed"] = float(speed_val)

        if "denoise" in input_params:
            denoise_val = input_params["denoise"]
            if not isinstance(denoise_val, bool):
                raise AppException(
                    status_code=422,
                    title="Invalid Denoise Setting",
                    detail="Denoise parameter must be a boolean (true or false).",
                    code="INVALID_PARAMETER_VALUE",
                )
            sanitized_params["denoise"] = denoise_val

        if "speaker" in input_params:
            speaker_val = str(input_params["speaker"]).lower()
            allowed_speakers = params_schema.get("speaker", {}).get("enum", [])
            if allowed_speakers and speaker_val not in [s.lower() for s in allowed_speakers]:
                raise AppException(
                    status_code=422,
                    title="Invalid Speaker",
                    detail=f"Speaker '{speaker_val}' is not valid for engine '{req.engine_id}'. Allowed: {allowed_speakers}",
                    code="INVALID_PARAMETER_VALUE",
                )
            sanitized_params["speaker"] = speaker_val

        payload = req.model_dump()
        payload["parameters"] = sanitized_params
        return payload

    @staticmethod
    async def submit_speech_job(
        db: AsyncSession,
        req: TTSJobSubmitRequest,
        current_user: User,
    ) -> JobRecord:
        """
        Submits a speech synthesis job into the durable SQLite queue.
        Enforces idempotency and payload collision checks (409 Conflict).
        """
        # 1. Idempotency Check
        if req.idempotency_key:
            stmt = select(JobRecord).where(
                JobRecord.user_id == current_user.id,
                JobRecord.idempotency_key == req.idempotency_key,
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing_payload = existing.payload_data or {}
                submitted_payload = req.model_dump()
                # Compare semantic payload fields (ignore idempotency_key itself)
                compare_keys = ["text", "engine_id", "language", "voice_id", "speed"]
                differs = any(existing_payload.get(k) != submitted_payload.get(k) for k in compare_keys)
                if differs:
                    raise AppException(
                        status_code=409,
                        title="Idempotency Conflict",
                        detail=f"Idempotency key '{req.idempotency_key}' was previously used with a different request payload.",
                        code="IDEMPOTENCY_CONFLICT",
                    )
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

        # 3. Comprehensive Engine Capability & Parameter Contract Validation
        sanitized_payload = await DurableQueueService._validate_and_sanitize_request(
            db=db,
            engine_rec=engine_rec,
            req=req,
            current_user=current_user,
        )

        # Determine resource type
        device_target = (engine_rec.device_target or "cpu").lower()
        resource_type = "gpu" if device_target == "gpu" or "qwen" in req.engine_id.lower() else "cpu"

        # 4. Resource & Quota Checks
        # A. Outstanding active/queued jobs limit per user
        active_states = [JobState.QUEUED.value, JobState.PREPARING.value, JobState.RUNNING.value]
        outstanding_stmt = (
            select(func.count(JobRecord.id))
            .where(
                JobRecord.user_id == current_user.id,
                JobRecord.status.in_(active_states),
            )
        )
        outstanding_res = await db.execute(outstanding_stmt)
        outstanding_count = outstanding_res.scalar() or 0
        if outstanding_count >= settings.MAX_OUTSTANDING_JOBS_PER_USER:
            raise AppException(
                status_code=429,
                title="Job Submission Limit Exceeded",
                detail=f"User has reached the maximum limit of {settings.MAX_OUTSTANDING_JOBS_PER_USER} active/queued jobs. Please wait for current jobs to complete.",
                code="TOO_MANY_OUTSTANDING_JOBS",
            )

        # B. User Storage Quota Check & Atomic Capacity Reservation
        estimated_output_bytes = max(1024 * 1024, len(req.text) * 10000)
        await UserQuotaService.assert_quota_available(
            db=db,
            user=current_user,
            expected_additional_bytes=estimated_output_bytes,
        )

        job_id = str(uuid.uuid4())

        # 5. Enqueue into SQLite WAL
        job = JobRecord(
            id=job_id,
            user_id=current_user.id,
            engine_id=req.engine_id,
            idempotency_key=req.idempotency_key,
            job_type="tts",
            status=JobState.QUEUED.value,
            progress_percent=0,
            priority=req.priority,
            resource_type=resource_type,
            attempt_count=0,
            max_retries=3,
            payload_data=sanitized_payload,
            queued_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()

        # Bind capacity reservation to the flushed job
        await UserQuotaService.reserve_capacity(
            db=db,
            user=current_user.id,
            estimated_bytes=estimated_output_bytes,
            reservation_type="speech_job",
            job_id=job_id,
            timeout_seconds=3600,
        )
        await db.commit()
        await db.refresh(job)

        # Emit queued event
        await event_service.emit_event(
            db=db,
            job_id=job.id,
            event_type="status_change",
            data={
                "status": JobState.QUEUED.value,
                "priority": job.priority,
                "resource_type": job.resource_type,
                "attempt_count": job.attempt_count,
            },
        )
        await db.commit()

        return job

    @staticmethod
    async def claim_next_job(
        worker_id: str,
        lease_duration_seconds: int = 30,
    ) -> Optional[JobRecord]:
        """
        Atomically claims the highest priority ready job whose resource requirements can be satisfied.
        Guarantees no two workers or threads can claim the same job concurrently.
        """
        now = datetime.now(timezone.utc)

        async with database.AsyncSessionLocal() as session:
            # 1. Fetch candidate jobs ready for execution (up to 50)
            stmt = (
                select(JobRecord)
                .where(
                    JobRecord.status == JobState.QUEUED.value,
                    or_(JobRecord.scheduled_at.is_(None), JobRecord.scheduled_at <= now),
                )
                .order_by(JobRecord.priority.desc(), JobRecord.queued_at.asc())
                .limit(50)
            )
            res = await session.execute(stmt)
            candidates = list(res.scalars().all())

            if not candidates:
                return None

            # 2. Fair Resource Scheduling (Persistent State Anti-Starvation & Head-of-Line Priority Precedence):
            user_ids = {c.user_id for c in candidates if c.user_id}
            user_active_counts: Dict[str, int] = {uid: 0 for uid in user_ids}
            user_last_dispatched: Dict[Tuple[str, str], datetime] = {}

            if user_ids:
                active_counts_stmt = (
                    select(JobRecord.user_id, func.count(JobRecord.id))
                    .where(
                        JobRecord.user_id.in_(list(user_ids)),
                        JobRecord.status.in_([JobState.PREPARING.value, JobState.RUNNING.value]),
                    )
                    .group_by(JobRecord.user_id)
                )
                counts_res = await session.execute(active_counts_stmt)
                for uid, count in counts_res.all():
                    user_active_counts[uid] = count

                sched_states_stmt = select(UserSchedulingStateRecord).where(
                    UserSchedulingStateRecord.user_id.in_(list(user_ids))
                )
                sched_states_res = await session.execute(sched_states_stmt)
                for state in sched_states_res.scalars().all():
                    user_last_dispatched[(state.user_id, state.resource_type)] = state.last_dispatched_at

            epoch_min = datetime.min.replace(tzinfo=timezone.utc)

            # Sort candidates fairly:
            # Tier 1: Higher priority precedence (-c.priority)
            # Tier 2: Within same priority, least active user first across in-flight jobs (user_active_counts)
            # Tier 3: Within same active count, anti-starvation fair-share per resource (least recently dispatched user first)
            # Tier 4: FIFO within same user (c.queued_at)
            def candidate_sort_key(c: JobRecord):
                res_t = c.resource_type or "cpu"
                last_disp = user_last_dispatched.get((c.user_id, res_t)) or epoch_min
                if last_disp.tzinfo is None:
                    last_disp = last_disp.replace(tzinfo=timezone.utc)
                q_at = c.queued_at or now
                if q_at.tzinfo is None:
                    q_at = q_at.replace(tzinfo=timezone.utc)
                return (
                    -c.priority,
                    user_active_counts.get(c.user_id, 0),
                    last_disp,
                    q_at,
                )

            sorted_candidates = sorted(candidates, key=candidate_sort_key)

            for candidate in sorted_candidates:
                res_type = candidate.resource_type or "cpu"
                if not await resource_manager.can_acquire(res_type, session, exclude_job_id=candidate.id):
                    # Update waiting reason if not already set
                    if candidate.waiting_reason != f"Awaiting {res_type.upper()} slot":
                        candidate.waiting_reason = f"Awaiting {res_type.upper()} slot"
                        await session.commit()
                    continue

                attempt_id = str(uuid.uuid4())
                lease_expires = now + timedelta(seconds=lease_duration_seconds)

                # Atomic claim update on specific candidate id
                claim_stmt = (
                    update(JobRecord)
                    .where(
                        JobRecord.id == candidate.id,
                        JobRecord.status == JobState.QUEUED.value,
                    )
                    .values(
                        status=JobState.PREPARING.value,
                        locked_by=worker_id,
                        lease_expires_at=lease_expires,
                        attempt_count=JobRecord.attempt_count + 1,
                        current_attempt_id=attempt_id,
                        waiting_reason=None,
                        heartbeat_at=now,
                    )
                )
                claim_res = await session.execute(claim_stmt)
                if claim_res.rowcount == 1:
                    # Acquired in database! Now acquire slot in resource manager
                    slot_acquired = await resource_manager.acquire(res_type, candidate.id, session)
                    if not slot_acquired:
                        # Rollback db claim if slot acquisition failed (defensive)
                        await session.rollback()
                        continue

                    # Update persistent user scheduling state for fair-share dispatch accounting
                    sched_stmt = select(UserSchedulingStateRecord).where(
                        UserSchedulingStateRecord.user_id == candidate.user_id,
                        UserSchedulingStateRecord.resource_type == res_type,
                    )
                    sched_res = await session.execute(sched_stmt)
                    sched_rec = sched_res.scalar_one_or_none()
                    if not sched_rec:
                        sched_rec = UserSchedulingStateRecord(
                            user_id=candidate.user_id,
                            resource_type=res_type,
                            last_dispatched_at=now,
                            dispatched_count=1,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(sched_rec)
                    else:
                        sched_rec.last_dispatched_at = now
                        sched_rec.dispatched_count += 1
                        sched_rec.updated_at = now

                    await session.commit()

                    # Fetch fresh claimed job
                    fetch_stmt = select(JobRecord).where(JobRecord.id == candidate.id)
                    fetched_res = await session.execute(fetch_stmt)
                    claimed_job = fetched_res.scalar_one()

                    # Emit preparing event
                    await event_service.emit_event(
                        db=session,
                        job_id=claimed_job.id,
                        event_type="status_change",
                        data={
                            "status": JobState.PREPARING.value,
                            "attempt_count": claimed_job.attempt_count,
                            "attempt_id": attempt_id,
                            "locked_by": worker_id,
                            "lease_expires_at": lease_expires.isoformat(),
                        },
                    )
                    await session.commit()
                    return claimed_job

            return None

    @staticmethod
    async def heartbeat(
        job_id: str,
        attempt_id: str,
        extend_seconds: int = 30,
        progress_percent: Optional[int] = None,
    ) -> bool:
        """
        Renews the lease for an active job if the attempt token matches.
        Rejects stale attempts whose lease was revoked or expired.
        """
        now = datetime.now(timezone.utc)
        lease_expires = now + timedelta(seconds=extend_seconds)

        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()

            if not job:
                return False

            # Fencing token check
            if job.current_attempt_id != attempt_id:
                return False

            if job.status not in (JobState.PREPARING.value, JobState.RUNNING.value):
                return False

            job.lease_expires_at = lease_expires
            job.heartbeat_at = now
            if progress_percent is not None:
                job.progress_percent = max(job.progress_percent, progress_percent)

            # Renew associated storage quota reservation to prevent premature expiration
            await UserQuotaService.renew_job_reservation(session, job.id, extend_seconds=1800)

            await session.commit()

            # Emit heartbeat / progress event
            await event_service.emit_event(
                db=session,
                job_id=job.id,
                event_type="progress" if progress_percent is not None else "heartbeat",
                data={
                    "status": job.status,
                    "progress_percent": job.progress_percent,
                    "lease_expires_at": lease_expires.isoformat(),
                    "heartbeat_at": now.isoformat(),
                },
            )
            await session.commit()
            return True

    @staticmethod
    async def mark_running(
        job_id: str,
        attempt_id: str,
        worker_id: str,
    ) -> bool:
        """
        Transitions job from PREPARING to RUNNING.
        """
        now = datetime.now(timezone.utc)
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()

            if not job or job.current_attempt_id != attempt_id:
                return False

            JobStateMachine.validate_transition(job.status, JobState.RUNNING.value)

            job.status = JobState.RUNNING.value
            job.worker_id = worker_id
            job.started_at = now
            job.progress_percent = max(job.progress_percent, 10)
            await session.commit()

            await event_service.emit_event(
                db=session,
                job_id=job.id,
                event_type="status_change",
                data={
                    "status": JobState.RUNNING.value,
                    "started_at": now.isoformat(),
                    "worker_id": worker_id,
                },
            )
            await session.commit()
            return True

    @staticmethod
    async def complete_job(
        job_id: str,
        attempt_id: str,
        artifact_id: str,
    ) -> bool:
        """
        Completes a running job, binds artifact, releases resource slot, and verifies fencing token.
        Rejects stale worker attempts.
        """
        now = datetime.now(timezone.utc)
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()

            if not job:
                return False

            # Strict Fencing Token Validation
            if job.current_attempt_id != attempt_id:
                raise FencingTokenError(job_id, attempt_id, job.current_attempt_id)

            if job.status == JobState.CANCELLED.value:
                # If job was cancelled while worker was finishing, release slot and keep cancelled
                await resource_manager.release_all(job.id)
                return False

            JobStateMachine.validate_transition(job.status, JobState.COMPLETED.value)

            job.status = JobState.COMPLETED.value
            job.progress_percent = 100
            job.artifact_id = artifact_id
            job.finished_at = now
            job.waiting_reason = None
            job.lease_expires_at = None

            from ..models.artifact import ArtifactRecord
            art_rec = await session.get(ArtifactRecord, artifact_id)
            actual_bytes = art_rec.file_size_bytes if art_rec else 0
            await UserQuotaService.commit_job_reservation(session, job.id, actual_bytes)

            await resource_manager.release_all(job.id)
            await session.commit()

            await event_service.emit_event(
                db=session,
                job_id=job.id,
                event_type="completed",
                data={
                    "status": JobState.COMPLETED.value,
                    "artifact_id": artifact_id,
                    "finished_at": now.isoformat(),
                    "progress_percent": 100,
                },
            )
            await session.commit()
            return True

    @staticmethod
    async def fail_job(
        job_id: str,
        attempt_id: Optional[str],
        error_code: str,
        error_message: str,
        retryable: bool = False,
    ) -> None:
        """
        Handles job failure with automatic exponential backoff retry if retryable and under max_retries.
        """
        now = datetime.now(timezone.utc)
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()

            if not job:
                return

            # If attempt_id provided, ensure it's not a stale attempt failing
            if attempt_id and job.current_attempt_id != attempt_id:
                return

            await resource_manager.release_all(job.id)

            if retryable and job.attempt_count < job.max_retries:
                # Exponential backoff: base 2.0s * 2^(attempt-1)
                backoff_delay = 2.0 * (2 ** max(0, job.attempt_count - 1))
                scheduled_time = now + timedelta(seconds=backoff_delay)

                JobStateMachine.validate_transition(job.status, JobState.QUEUED.value)
                job.status = JobState.QUEUED.value
                job.scheduled_at = scheduled_time
                job.waiting_reason = f"Retrying in {backoff_delay:.1f}s (Attempt {job.attempt_count}/{job.max_retries})"
                job.locked_by = None
                job.lease_expires_at = None
                await session.commit()

                await event_service.emit_event(
                    db=session,
                    job_id=job.id,
                    event_type="status_change",
                    data={
                        "status": JobState.QUEUED.value,
                        "attempt_count": job.attempt_count,
                        "retry_scheduled_at": scheduled_time.isoformat(),
                        "error_code": error_code,
                        "error_message": error_message,
                    },
                )
                await session.commit()
            else:
                JobStateMachine.validate_transition(job.status, JobState.FAILED.value)
                job.status = JobState.FAILED.value
                job.error_details = {
                    "code": error_code,
                    "message": error_message,
                    "attempt_count": job.attempt_count,
                }
                job.finished_at = now
                job.locked_by = None
                job.lease_expires_at = None
                job.waiting_reason = None

                await UserQuotaService.release_job_reservation(session, job.id)
                await session.commit()

                await event_service.emit_event(
                    db=session,
                    job_id=job.id,
                    event_type="failed",
                    data={
                        "status": JobState.FAILED.value,
                        "error_details": job.error_details,
                        "finished_at": now.isoformat(),
                    },
                )
                await session.commit()

    @staticmethod
    async def cancel_job(
        job_id: str,
        current_user: User,
    ) -> JobRecord:
        """
        Cancels a queued or active job. Rejects cancellation for completed/failed/cancelled jobs.
        """
        now = datetime.now(timezone.utc)
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
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
                    detail="You do not have permission to cancel this job.",
                    code="FORBIDDEN_JOB_ACCESS",
                )

            if job.status in (JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value):
                raise AppException(
                    status_code=400,
                    title="Cannot Cancel Job",
                    detail=f"Cannot cancel job in terminal state '{job.status}'.",
                    code="INVALID_JOB_STATE",
                )

            JobStateMachine.validate_transition(job.status, JobState.CANCELLED.value)

            job.status = JobState.CANCELLED.value
            job.finished_at = now
            job.waiting_reason = None
            job.lease_expires_at = None

            await resource_manager.release_all(job.id)
            await UserQuotaService.release_job_reservation(session, job.id)
            await session.commit()

            await event_service.emit_event(
                db=session,
                job_id=job.id,
                event_type="cancelled",
                data={
                    "status": JobState.CANCELLED.value,
                    "finished_at": now.isoformat(),
                },
            )
            await session.commit()
            return job

    @staticmethod
    async def retry_failed_job(
        job_id: str,
        current_user: User,
    ) -> JobRecord:
        """
        Manually retries a failed job, resetting attempts and re-enqueueing.
        """
        now = datetime.now(timezone.utc)
        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(JobRecord.id == job_id)
            res = await session.execute(stmt)
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
                    detail="You do not have permission to retry this job.",
                    code="FORBIDDEN_JOB_ACCESS",
                )

            if job.status != JobState.FAILED.value:
                raise AppException(
                    status_code=400,
                    title="Cannot Retry Job",
                    detail=f"Only failed jobs can be manually retried (current state: '{job.status}').",
                    code="INVALID_JOB_STATE",
                )

            JobStateMachine.validate_transition(job.status, JobState.QUEUED.value)

            job.status = JobState.QUEUED.value
            job.attempt_count = 0
            job.scheduled_at = None
            job.error_details = None
            job.waiting_reason = None
            job.progress_percent = 0
            job.started_at = None
            job.finished_at = None
            job.locked_by = None
            job.lease_expires_at = None
            job.heartbeat_at = None

            await session.commit()

            await event_service.emit_event(
                db=session,
                job_id=job.id,
                event_type="status_change",
                data={
                    "status": JobState.QUEUED.value,
                    "reason": "Manual retry initiated by user",
                },
            )
            await session.commit()
            return job

    @staticmethod
    async def reclaim_expired_leases() -> int:
        """
        Finds jobs in PREPARING or RUNNING with expired leases and reclaims or fails them.
        """
        now = datetime.now(timezone.utc)
        reclaimed_count = 0

        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(
                JobRecord.status.in_([JobState.PREPARING.value, JobState.RUNNING.value]),
                JobRecord.lease_expires_at < now,
            )
            res = await session.execute(stmt)
            expired_jobs = res.scalars().all()

            for job in expired_jobs:
                reclaimed_count += 1
                await resource_manager.release_all(job.id)

                if job.attempt_count < job.max_retries:
                    backoff_delay = 2.0 * (2 ** max(0, job.attempt_count - 1))
                    scheduled_time = now + timedelta(seconds=backoff_delay)

                    job.status = JobState.QUEUED.value
                    job.scheduled_at = scheduled_time
                    job.waiting_reason = f"Reclaimed after lease expiration (Attempt {job.attempt_count}/{job.max_retries})"
                    job.locked_by = None
                    job.lease_expires_at = None

                    await event_service.emit_event(
                        db=session,
                        job_id=job.id,
                        event_type="status_change",
                        data={
                            "status": JobState.QUEUED.value,
                            "reason": "Lease expired, re-queued",
                            "attempt_count": job.attempt_count,
                            "retry_scheduled_at": scheduled_time.isoformat(),
                        },
                    )
                else:
                    job.status = JobState.FAILED.value
                    job.error_details = {
                        "code": "LEASE_EXPIRED",
                        "message": f"Job exceeded max retries ({job.max_retries}) due to lease expiration or worker timeouts.",
                    }
                    job.finished_at = now
                    job.locked_by = None
                    job.lease_expires_at = None
                    job.waiting_reason = None

                    await event_service.emit_event(
                        db=session,
                        job_id=job.id,
                        event_type="failed",
                        data={
                            "status": JobState.FAILED.value,
                            "error_details": job.error_details,
                            "finished_at": now.isoformat(),
                        },
                    )

            if expired_jobs:
                await session.commit()

        return reclaimed_count

    @staticmethod
    async def recover_on_startup() -> int:
        """
        Scans for stuck jobs from an unclean server shutdown and reclaims or fails them.
        """
        now = datetime.now(timezone.utc)
        recovered_count = 0

        async with database.AsyncSessionLocal() as session:
            stmt = select(JobRecord).where(
                JobRecord.status.in_([JobState.PREPARING.value, JobState.RUNNING.value])
            )
            res = await session.execute(stmt)
            stuck_jobs = res.scalars().all()

            for job in stuck_jobs:
                recovered_count += 1
                await resource_manager.release_all(job.id)

                if job.attempt_count < job.max_retries:
                    job.status = JobState.QUEUED.value
                    job.scheduled_at = now
                    job.waiting_reason = "Recovered after server restart"
                    job.locked_by = None
                    job.lease_expires_at = None

                    await event_service.emit_event(
                        db=session,
                        job_id=job.id,
                        event_type="status_change",
                        data={
                            "status": JobState.QUEUED.value,
                            "reason": "Server restarted, job re-queued",
                        },
                    )
                else:
                    job.status = JobState.FAILED.value
                    job.error_details = {
                        "code": "SERVER_RESTARTED",
                        "message": "Worker process lost during server restart",
                    }
                    job.finished_at = now
                    job.locked_by = None
                    job.lease_expires_at = None
                    job.waiting_reason = None

                    await event_service.emit_event(
                        db=session,
                        job_id=job.id,
                        event_type="failed",
                        data={
                            "status": JobState.FAILED.value,
                            "error_details": job.error_details,
                            "finished_at": now.isoformat(),
                        },
                    )

            if stuck_jobs:
                await session.commit()

        return recovered_count
