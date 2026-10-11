"""
Voice Profile Service
Manages reusable, user-isolated cloned voice profiles.
Stores records in SQLite and persists profile metadata to user-owned storage
(settings.get_data_dir() / "voices" / user.id / {profile_id}.json),
completely isolating custom voices and avoiding writes to global Python packages.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import AppException
from ..models.asset import ReferenceAssetRecord
from ..models.user import User
from ..models.voice_profile import VoiceProfileRecord
from ..schemas.voice_profile import VoiceProfileCreate, VoiceProfileUpdate


class VoiceProfileService:
    @staticmethod
    def _get_user_voice_dir(user_id: str) -> Path:
        base_dir = settings.get_data_dir() / "voices" / user_id
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    async def create_profile(
        cls,
        db: AsyncSession,
        user: User,
        data: VoiceProfileCreate,
    ) -> VoiceProfileRecord:
        # 1. Verify Reference Audio Asset exists and belongs to user
        stmt_asset = select(ReferenceAssetRecord).where(ReferenceAssetRecord.id == data.reference_asset_id)
        res_asset = await db.execute(stmt_asset)
        asset_rec = res_asset.scalar_one_or_none()

        if not asset_rec:
            raise AppException(
                status_code=404,
                title="Reference Asset Not Found",
                detail=f"Reference audio asset '{data.reference_asset_id}' does not exist.",
                code="REFERENCE_ASSET_NOT_FOUND",
            )

        if asset_rec.user_id != user.id and getattr(user, "role", "user") != "admin":
            raise AppException(
                status_code=403,
                title="Access Denied",
                detail="You do not have authorization to create a voice profile from this reference asset.",
                code="FORBIDDEN_ASSET_ACCESS",
            )

        if not asset_rec.voice_use_consent:
            raise AppException(
                status_code=400,
                title="Voice Use Consent Required",
                detail="The referenced audio sample lacks verified voice-use consent.",
                code="VOICE_CONSENT_REQUIRED",
            )

        # 2. Create DB record
        profile = VoiceProfileRecord(
            user_id=user.id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            engine_id=data.engine_id,
            reference_asset_id=asset_rec.id,
        )
        profile.parameters = data.parameters or {}

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        # 3. Persist JSON metadata in user-isolated storage
        cls._save_profile_file(user.id, profile)

        return profile

    @classmethod
    def _save_profile_file(cls, user_id: str, profile: VoiceProfileRecord):
        user_dir = cls._get_user_voice_dir(user_id)
        file_path = user_dir / f"{profile.id}.json"
        data = {
            "id": profile.id,
            "user_id": profile.user_id,
            "name": profile.name,
            "description": profile.description,
            "engine_id": profile.engine_id,
            "reference_asset_id": profile.reference_asset_id,
            "parameters": profile.parameters,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    async def list_profiles(
        cls,
        db: AsyncSession,
        user: User,
    ) -> List[VoiceProfileRecord]:
        stmt = (
            select(VoiceProfileRecord)
            .where(VoiceProfileRecord.user_id == user.id)
            .order_by(VoiceProfileRecord.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_profile(
        cls,
        db: AsyncSession,
        profile_id: str,
        user: User,
    ) -> VoiceProfileRecord:
        stmt = select(VoiceProfileRecord).where(VoiceProfileRecord.id == profile_id)
        res = await db.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile:
            raise AppException(
                status_code=404,
                title="Voice Profile Not Found",
                detail=f"Voice profile '{profile_id}' does not exist.",
                code="VOICE_PROFILE_NOT_FOUND",
            )

        if profile.user_id != user.id and getattr(user, "role", "user") != "admin":
            raise AppException(
                status_code=403,
                title="Access Denied",
                detail="You do not have authorization to access this voice profile.",
                code="FORBIDDEN_PROFILE_ACCESS",
            )

        return profile

    @classmethod
    async def update_profile(
        cls,
        db: AsyncSession,
        profile_id: str,
        user: User,
        data: VoiceProfileUpdate,
    ) -> VoiceProfileRecord:
        profile = await cls.get_profile(db, profile_id, user)

        if data.name is not None:
            profile.name = data.name.strip()
        if data.description is not None:
            profile.description = data.description.strip()
        if data.parameters is not None:
            profile.parameters = data.parameters

        profile.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(profile)

        cls._save_profile_file(profile.user_id, profile)
        return profile

    @classmethod
    async def delete_profile(
        cls,
        db: AsyncSession,
        profile_id: str,
        user: User,
    ) -> bool:
        profile = await cls.get_profile(db, profile_id, user)

        # Remove local metadata file
        user_dir = cls._get_user_voice_dir(profile.user_id)
        file_path = user_dir / f"{profile.id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

        await db.delete(profile)
        await db.commit()
        return True
