"""
Audio Artifact Management Service
"""

import hashlib
import io
from pathlib import Path
import uuid
import wave

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import AppException
from ..models.artifact import ArtifactRecord
from ..models.user import User


class ArtifactService:
    @staticmethod
    async def create_artifact_from_bytes(
        db: AsyncSession,
        owner_id: str,
        audio_bytes: bytes,
        format: str = "wav",
        sample_rate: int = 44100,
        duration_seconds: float = 0.0,
    ) -> ArtifactRecord:
        artifact_id = str(uuid.uuid4())
        artifacts_dir = settings.get_data_dir() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        file_path = artifacts_dir / f"{artifact_id}.{format}"

        # Calculate SHA-256
        file_hash = hashlib.sha256(audio_bytes).hexdigest()
        file_size = len(audio_bytes)

        # Inspect WAV header for accurate duration and sample rate if WAV
        if format.lower() == "wav" and file_size >= 44:
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate > 0:
                        sample_rate = rate
                        duration_seconds = round(frames / float(rate), 2)
            except Exception:
                pass

        # Write to disk
        file_path.write_bytes(audio_bytes)

        record = ArtifactRecord(
            id=artifact_id,
            owner_id=owner_id,
            file_path=str(file_path),
            file_hash_sha256=file_hash,
            file_size_bytes=file_size,
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            format=format,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_artifact(
        db: AsyncSession,
        artifact_id: str,
        current_user: User,
    ) -> ArtifactRecord:
        stmt = select(ArtifactRecord).where(ArtifactRecord.id == artifact_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise AppException(
                status_code=404,
                title="Artifact Not Found",
                detail=f"Audio artifact '{artifact_id}' does not exist.",
                code="ARTIFACT_NOT_FOUND",
            )

        if record.owner_id != current_user.id and current_user.role != "admin":
            raise AppException(
                status_code=403,
                title="Forbidden",
                detail="You do not have permission to access this audio artifact.",
                code="FORBIDDEN_ARTIFACT_ACCESS",
            )

        # Confirm file exists on disk
        if not Path(record.file_path).exists():
            raise AppException(
                status_code=404,
                title="File Not Found",
                detail=f"Audio file for artifact '{artifact_id}' is missing from local storage.",
                code="ARTIFACT_FILE_MISSING",
            )

        return record

    @staticmethod
    async def delete_artifact(
        db: AsyncSession,
        artifact_id: str,
    ) -> bool:
        """
        Deletes artifact record from database and removes underlying audio file from disk.
        """
        stmt = select(ArtifactRecord).where(ArtifactRecord.id == artifact_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return False

        file_p = Path(record.file_path)
        if file_p.exists():
            try:
                file_p.unlink()
            except Exception:
                pass

        await db.delete(record)
        await db.commit()
        return True
