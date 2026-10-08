"""
Reference Audio Asset Management Service
Handles secure reference audio uploads, validation, storage, and access authorization.
"""

import hashlib
import io
from pathlib import Path
import uuid
import wave
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import AppException
from ..models.asset import ReferenceAssetRecord
from ..models.user import User

MAX_REF_AUDIO_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MIN_REF_AUDIO_DURATION_SEC = 0.5  # 0.5s minimum for testing & short prompts
MAX_REF_AUDIO_DURATION_SEC = 30.0  # 30s maximum to prevent resource exhaustion


class AssetService:
    @staticmethod
    async def upload_reference_audio(
        db: AsyncSession,
        user: User,
        file_bytes: bytes,
        original_filename: str,
        voice_use_consent: bool,
    ) -> ReferenceAssetRecord:
        # 1. Voice-use consent enforcement
        if not voice_use_consent:
            raise AppException(
                status_code=400,
                title="Voice Use Consent Required",
                detail="You must explicitly confirm legal consent to clone or use this voice reference.",
                code="VOICE_CONSENT_REQUIRED",
            )

        # 2. Maximum file size check
        if len(file_bytes) > MAX_REF_AUDIO_SIZE_BYTES:
            raise AppException(
                status_code=413,
                title="File Too Large",
                detail=f"Reference audio exceeds maximum size limit of {MAX_REF_AUDIO_SIZE_BYTES // (1024 * 1024)}MB.",
                code="FILE_TOO_LARGE",
            )

        # 3. Audio format and magic bytes inspection
        if len(file_bytes) < 44 or not (file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WAVE"):
            raise AppException(
                status_code=422,
                title="Invalid Audio Format",
                detail="Reference audio must be a valid RIFF/WAVE PCM audio file.",
                code="INVALID_AUDIO_FORMAT",
            )

        # 4. Parse WAV header and inspect duration, sample rate, channels
        try:
            with wave.open(io.BytesIO(file_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                sampwidth = wf.getsampwidth()
                frames = wf.getnframes()

                if channels not in (1, 2):
                    raise ValueError(f"Unsupported channel count: {channels} (only mono/stereo permitted)")
                if sample_rate < 8000 or sample_rate > 96000:
                    raise ValueError(f"Unsupported sample rate: {sample_rate}Hz (permitted 8000 - 96000Hz)")
                if sampwidth not in (1, 2, 3, 4):
                    raise ValueError(f"Unsupported sample width: {sampwidth * 8}-bit")

                duration_seconds = round(frames / float(sample_rate), 2)
        except Exception as exc:
            raise AppException(
                status_code=422,
                title="Corrupted Audio File",
                detail=f"Failed to parse WAV audio file: {exc}",
                code="CORRUPTED_AUDIO_FILE",
            )

        if duration_seconds < MIN_REF_AUDIO_DURATION_SEC:
            raise AppException(
                status_code=422,
                title="Audio Too Short",
                detail=f"Reference audio duration ({duration_seconds}s) is shorter than minimum allowed ({MIN_REF_AUDIO_DURATION_SEC}s).",
                code="AUDIO_TOO_SHORT",
            )

        if duration_seconds > MAX_REF_AUDIO_DURATION_SEC:
            raise AppException(
                status_code=422,
                title="Audio Too Long",
                detail=f"Reference audio duration ({duration_seconds}s) exceeds maximum allowed limit ({MAX_REF_AUDIO_DURATION_SEC}s).",
                code="AUDIO_TOO_LONG",
            )

        # 5. Path traversal protection: server-generated UUID identifier
        asset_id = str(uuid.uuid4())
        safe_dir = settings.get_data_dir() / "assets" / user.id
        safe_dir.mkdir(parents=True, exist_ok=True)
        safe_file_path = safe_dir / f"{asset_id}.wav"

        # Calculate SHA-256
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Write safely to host disk
        safe_file_path.write_bytes(file_bytes)

        # Sanitized filename for metadata
        safe_filename = Path(original_filename).name[:255] or "reference_voice.wav"

        # 6. Persist record with user ownership
        record = ReferenceAssetRecord(
            id=asset_id,
            user_id=user.id,
            filename=safe_filename,
            file_path=str(safe_file_path),
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            format="wav",
            voice_use_consent=voice_use_consent,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return record

    @staticmethod
    async def get_reference_asset(
        db: AsyncSession,
        asset_id: str,
        user: User,
    ) -> ReferenceAssetRecord:
        stmt = select(ReferenceAssetRecord).where(ReferenceAssetRecord.id == asset_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise AppException(
                status_code=404,
                title="Reference Asset Not Found",
                detail=f"Reference audio asset '{asset_id}' does not exist.",
                code="ASSET_NOT_FOUND",
            )

        # Per-user ownership check
        if record.user_id != user.id and getattr(user, "role", "user") != "admin":
            raise AppException(
                status_code=403,
                title="Access Denied",
                detail="You do not have authorization to access or use this reference audio asset.",
                code="FORBIDDEN_ASSET_ACCESS",
            )

        return record

    @staticmethod
    async def list_user_reference_assets(
        db: AsyncSession,
        user: User,
    ) -> List[ReferenceAssetRecord]:
        stmt = (
            select(ReferenceAssetRecord)
            .where(ReferenceAssetRecord.user_id == user.id)
            .order_by(ReferenceAssetRecord.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_reference_asset(
        db: AsyncSession,
        asset_id: str,
        user: User,
    ) -> bool:
        record = await AssetService.get_reference_asset(db, asset_id, user)

        # Remove physical file if exists
        p = Path(record.file_path)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

        await db.delete(record)
        await db.commit()
        return True
