"""
User Storage Quota Accounting & Atomic Capacity Reservation Service
Tracks per-user disk usage across artifacts, reference assets, master exports, and active reservations.
Prevents silent limit overflow under concurrency without destructively deleting existing user files.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Union, Optional
import uuid

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from ..config import settings
from ..core.errors import AppException
from ..models.user import User
from ..models.artifact import ArtifactRecord
from ..models.asset import ReferenceAssetRecord
from ..models.export import ProjectExportRecord
from ..models.project import ProjectRecord
from ..models.storage_reservation import StorageReservationRecord
from ..models.job import JobRecord


class UserQuotaService:
    @staticmethod
    async def cleanup_expired_reservations(db: AsyncSession) -> int:
        """
        Marks active reservations whose lease has expired as EXPIRED,
        while strictly protecting active, healthy jobs (QUEUED, PREPARING, RUNNING).
        Recovers truly abandoned capacity after worker or client crashes.
        """
        now = datetime.now(timezone.utc)

        # 1. Non-job reservations (e.g. abandoned exports or asset uploads) that expired
        stmt_standalone = (
            update(StorageReservationRecord)
            .where(
                StorageReservationRecord.status == "ACTIVE",
                StorageReservationRecord.job_id.is_(None),
                StorageReservationRecord.expires_at <= now,
            )
            .values(status="EXPIRED", updated_at=now)
        )
        res_standalone = await db.execute(stmt_standalone)
        expired_count = res_standalone.rowcount or 0

        # 2. Job-associated reservations: only expire if job is terminated or abandoned
        stmt_job_res = select(StorageReservationRecord).where(
            StorageReservationRecord.status == "ACTIVE",
            StorageReservationRecord.job_id.is_not(None),
            StorageReservationRecord.expires_at <= now,
        )
        res_cand = await db.execute(stmt_job_res)
        candidates = res_cand.scalars().all()

        for cand in candidates:
            stmt_job = select(JobRecord).where(JobRecord.id == cand.job_id)
            res_job = await db.execute(stmt_job)
            job = res_job.scalar_one_or_none()

            is_dead = False
            if not job:
                is_dead = True
            elif job.status in ("completed", "failed", "cancelled"):
                is_dead = True
            elif job.status in ("preparing", "running"):
                if job.lease_expires_at:
                    job_lease = job.lease_expires_at if job.lease_expires_at.tzinfo else job.lease_expires_at.replace(tzinfo=timezone.utc)
                    if job_lease <= now:
                        is_dead = True
                else:
                    is_dead = True
            # Note: if job is 'queued', the job is legitimately waiting for a hardware slot; do NOT expire!

            if is_dead:
                cand.status = "EXPIRED"
                cand.updated_at = now
                expired_count += 1

        await db.flush()
        return expired_count

    @staticmethod
    async def renew_job_reservation(
        db: AsyncSession,
        job_id: str,
        extend_seconds: int = 1800,
    ) -> bool:
        """
        Extends the lease expiration for any ACTIVE reservations associated with an active job.
        Called during worker heartbeats to guarantee healthy long-running jobs are never reclaimed.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(StorageReservationRecord)
            .where(
                StorageReservationRecord.job_id == job_id,
                StorageReservationRecord.status == "ACTIVE",
            )
            .values(
                expires_at=now + timedelta(seconds=extend_seconds),
                updated_at=now,
            )
        )
        res = await db.execute(stmt)
        return (res.rowcount or 0) > 0

    @staticmethod
    async def get_user_storage_usage(
        db: AsyncSession,
        user: Union[User, str],
        include_active_reservations: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculates exact cumulative storage consumed by user across all audio files
        and in-flight capacity reservations.
        """
        if isinstance(user, User):
            user_id = user.id
            quota_mb = user.storage_quota_mb if user.storage_quota_mb is not None else settings.USER_STORAGE_QUOTA_MB
        else:
            user_id = str(user)
            user_rec = await db.get(User, user_id)
            quota_mb = user_rec.storage_quota_mb if (user_rec and user_rec.storage_quota_mb is not None) else settings.USER_STORAGE_QUOTA_MB

        now = datetime.now(timezone.utc)

        # 1. Total bytes in audio artifacts
        art_stmt = select(func.coalesce(func.sum(ArtifactRecord.file_size_bytes), 0)).where(
            ArtifactRecord.owner_id == user_id
        )
        art_bytes = (await db.execute(art_stmt)).scalar() or 0

        # 2. Total bytes in reference audio assets
        ref_stmt = select(func.coalesce(func.sum(ReferenceAssetRecord.file_size_bytes), 0)).where(
            ReferenceAssetRecord.user_id == user_id
        )
        ref_bytes = (await db.execute(ref_stmt)).scalar() or 0

        # 3. Total bytes in master project exports
        exp_stmt = (
            select(func.coalesce(func.sum(ProjectExportRecord.file_size_bytes), 0))
            .join(ProjectRecord, ProjectExportRecord.project_id == ProjectRecord.id)
            .where(ProjectRecord.user_id == user_id)
        )
        exp_bytes = (await db.execute(exp_stmt)).scalar() or 0

        # 4. Total bytes in active (unexpired) reservations
        res_bytes = 0
        if include_active_reservations:
            res_stmt = select(func.coalesce(func.sum(StorageReservationRecord.reserved_bytes), 0)).where(
                StorageReservationRecord.user_id == user_id,
                StorageReservationRecord.status == "ACTIVE",
                StorageReservationRecord.expires_at > now,
            )
            res_bytes = (await db.execute(res_stmt)).scalar() or 0

        persisted_bytes = int(art_bytes + ref_bytes + exp_bytes)
        total_used_bytes = int(persisted_bytes + res_bytes)
        total_used_mb = round(total_used_bytes / (1024 * 1024), 2)

        # Quota configuration (0 or negative means unlimited)
        if quota_mb > 0:
            quota_bytes = quota_mb * 1024 * 1024
            percent_used = round(min(100.0, (total_used_bytes / quota_bytes) * 100.0), 2)
            remaining_bytes = max(0, quota_bytes - total_used_bytes)
        else:
            quota_bytes = 0
            percent_used = 0.0
            remaining_bytes = 999999999999

        return {
            "persisted_bytes": persisted_bytes,
            "reserved_bytes": res_bytes,
            "used_bytes": total_used_bytes,
            "used_mb": total_used_mb,
            "quota_mb": float(quota_mb),
            "quota_bytes": quota_bytes,
            "remaining_bytes": remaining_bytes,
            "percent_used": percent_used,
        }

    @staticmethod
    async def reserve_capacity(
        db: AsyncSession,
        user: Union[User, str],
        estimated_bytes: int,
        reservation_type: str,
        job_id: Optional[str] = None,
        timeout_seconds: int = 1800,
    ) -> StorageReservationRecord:
        """
        Transactionally reserves storage capacity before commencing resource-intensive output.
        Raises HTTP 413 USER_STORAGE_QUOTA_EXCEEDED if limit would be breached.
        """
        user_id = user.id if isinstance(user, User) else str(user)
        now = datetime.now(timezone.utc)

        # Clean expired reservations first
        await UserQuotaService.cleanup_expired_reservations(db)

        # Check available quota including all currently active reservations
        usage = await UserQuotaService.get_user_storage_usage(db, user, include_active_reservations=True)
        quota_mb = usage["quota_mb"]

        if quota_mb > 0:
            quota_bytes = usage["quota_bytes"]
            future_bytes = usage["used_bytes"] + estimated_bytes
            if future_bytes > quota_bytes:
                raise AppException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    title="Storage Quota Exceeded",
                    detail=f"User storage quota exceeded. Current used+reserved: {usage['used_mb']} MB, Incoming estimate: {round(estimated_bytes/(1024*1024), 2)} MB, Limit: {quota_mb} MB.",
                    code="USER_STORAGE_QUOTA_EXCEEDED",
                    extra={
                        "used_bytes": usage["used_bytes"],
                        "estimated_bytes": estimated_bytes,
                        "quota_bytes": quota_bytes,
                        "remaining_bytes": usage["remaining_bytes"],
                    },
                )

        # Create persistent active reservation record
        reservation = StorageReservationRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            job_id=job_id,
            reservation_type=reservation_type,
            reserved_bytes=estimated_bytes,
            status="ACTIVE",
            expires_at=now + timedelta(seconds=timeout_seconds),
            created_at=now,
            updated_at=now,
        )
        db.add(reservation)
        await db.flush()
        return reservation

    @staticmethod
    async def commit_reservation(
        db: AsyncSession,
        reservation_id: str,
        actual_bytes: int,
    ) -> None:
        """
        Finalizes an active reservation into permanent storage.
        Reconciles any disparity between estimated and actual bytes.
        Rejects stale workers attempting to commit expired/reclaimed reservations.
        """
        now = datetime.now(timezone.utc)
        stmt = select(StorageReservationRecord).where(StorageReservationRecord.id == reservation_id)
        res = await db.execute(stmt)
        reservation = res.scalar_one_or_none()
        if not reservation:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation {reservation_id} not found.",
                code="RESERVATION_NOT_FOUND",
            )

        if reservation.status != "ACTIVE":
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                title="Stale Reservation",
                detail=f"Cannot commit reservation {reservation_id}: status is {reservation.status} (expired or reclaimed).",
                code="RESERVATION_STALE_OR_RECLAIMED",
            )

        # Reconcile actual bytes into permanent accounting
        reservation.reserved_bytes = actual_bytes
        reservation.status = "COMMITTED"
        reservation.updated_at = now
        await db.flush()

    @staticmethod
    async def commit_job_reservation(
        db: AsyncSession,
        job_id: str,
        actual_bytes: int,
    ) -> None:
        """
        Finalizes the active reservation associated with a specific TTS job.
        Rejects stale workers if reservation was already expired or reclaimed.
        """
        stmt = select(StorageReservationRecord).where(
            StorageReservationRecord.job_id == job_id,
        )
        res = await db.execute(stmt)
        reservations = res.scalars().all()
        if not reservations:
            return

        for r in reservations:
            if r.status != "ACTIVE":
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    title="Stale Reservation",
                    detail=f"Cannot commit reservation for job {job_id}: reservation is {r.status} (expired or reclaimed).",
                    code="RESERVATION_STALE_OR_RECLAIMED",
                )
            await UserQuotaService.commit_reservation(db, r.id, actual_bytes)

    @staticmethod
    async def release_reservation(
        db: AsyncSession,
        reservation_id: str,
    ) -> None:
        """
        Releases an active reservation after failure or cancellation.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(StorageReservationRecord)
            .where(StorageReservationRecord.id == reservation_id)
            .values(status="RELEASED", updated_at=now)
        )
        await db.execute(stmt)
        await db.flush()

    @staticmethod
    async def release_job_reservation(
        db: AsyncSession,
        job_id: str,
    ) -> None:
        """
        Releases any active reservations associated with a failed or cancelled job.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(StorageReservationRecord)
            .where(
                StorageReservationRecord.job_id == job_id,
                StorageReservationRecord.status == "ACTIVE",
            )
            .values(status="RELEASED", updated_at=now)
        )
        await db.execute(stmt)
        await db.flush()

    @staticmethod
    async def assert_quota_available(
        db: AsyncSession,
        user: Union[User, str],
        incoming_bytes: int = 0,
        expected_additional_bytes: Any = None,
    ) -> None:
        """
        Direct assertion helper for single-transaction checks.
        """
        effective_incoming = expected_additional_bytes if expected_additional_bytes is not None else incoming_bytes
        usage = await UserQuotaService.get_user_storage_usage(db, user, include_active_reservations=True)
        quota_mb = usage["quota_mb"]
        if quota_mb <= 0:
            return  # Unlimited quota

        quota_bytes = usage["quota_bytes"]
        future_bytes = usage["used_bytes"] + effective_incoming

        if future_bytes > quota_bytes:
            raise AppException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                title="Storage Quota Exceeded",
                detail=f"User storage quota exceeded. Current used+reserved: {usage['used_mb']} MB, Incoming: {round(effective_incoming/(1024*1024), 2)} MB, Limit: {quota_mb} MB.",
                code="USER_STORAGE_QUOTA_EXCEEDED",
                extra={
                    "used_bytes": usage["used_bytes"],
                    "incoming_bytes": effective_incoming,
                    "quota_bytes": quota_bytes,
                },
            )
