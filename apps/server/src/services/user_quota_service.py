"""
User Storage Quota Accounting & Reservation Service
Tracks per-user disk usage across artifacts, reference assets, and master exports.
Prevents silent limit overflow without destructively deleting existing user files.
"""

from typing import Dict, Any, Union
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from ..config import settings
from ..core.errors import AppException
from ..models.user import User
from ..models.artifact import ArtifactRecord
from ..models.asset import ReferenceAssetRecord
from ..models.export import ProjectExportRecord
from ..models.project import ProjectRecord


class UserQuotaService:
    @staticmethod
    async def get_user_storage_usage(db: AsyncSession, user: Union[User, str]) -> Dict[str, Any]:
        """
        Calculates exact cumulative storage consumed by user across all audio files.
        Accepts either a User model instance or a string user_id.
        """
        if isinstance(user, User):
            user_id = user.id
            quota_mb = user.storage_quota_mb if user.storage_quota_mb is not None else settings.USER_STORAGE_QUOTA_MB
        else:
            user_id = str(user)
            user_rec = await db.get(User, user_id)
            quota_mb = user_rec.storage_quota_mb if (user_rec and user_rec.storage_quota_mb is not None) else settings.USER_STORAGE_QUOTA_MB

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

        total_used_bytes = int(art_bytes + ref_bytes + exp_bytes)
        total_used_mb = round(total_used_bytes / (1024 * 1024), 2)

        # Quota configuration
        if quota_mb > 0:
            quota_bytes = quota_mb * 1024 * 1024
            percent_used = round(min(100.0, (total_used_bytes / quota_bytes) * 100.0), 2)
        else:
            quota_bytes = 0
            percent_used = 0.0

        return {
            "used_bytes": total_used_bytes,
            "used_mb": total_used_mb,
            "quota_mb": float(quota_mb),
            "quota_bytes": quota_bytes,
            "percent_used": percent_used,
        }

    @staticmethod
    async def assert_quota_available(
        db: AsyncSession,
        user: Union[User, str],
        incoming_bytes: int = 0,
        expected_additional_bytes: Any = None,
    ) -> None:
        """
        Asserts that user has sufficient remaining storage quota.
        Raises HTTP 413 USER_STORAGE_QUOTA_EXCEEDED if limit would be breached.
        """
        if expected_additional_bytes is not None:
            effective_incoming = expected_additional_bytes
        else:
            effective_incoming = incoming_bytes

        usage = await UserQuotaService.get_user_storage_usage(db, user)
        quota_mb = usage["quota_mb"]
        if quota_mb <= 0:
            return  # Unlimited quota

        quota_bytes = usage["quota_bytes"]
        future_bytes = usage["used_bytes"] + effective_incoming

        if future_bytes > quota_bytes:
            raise AppException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                title="Storage Quota Exceeded",
                detail=f"User storage quota exceeded. Current: {usage['used_mb']} MB, Incoming: {round(effective_incoming/(1024*1024), 2)} MB, Limit: {quota_mb} MB.",
                code="USER_STORAGE_QUOTA_EXCEEDED",
                extra={
                    "used_bytes": usage["used_bytes"],
                    "incoming_bytes": effective_incoming,
                    "quota_bytes": quota_bytes,
                },
            )
