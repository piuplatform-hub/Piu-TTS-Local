"""
Audio Artifacts API Endpoints (v1)
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.artifact import ArtifactResponse
from ...core.errors import AppException
from ...services.auth_service import get_current_user
from ...services.artifact_service import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_metadata(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get metadata for an audio artifact (file size, duration, sample rate, format).
    """
    artifact = await ArtifactService.get_artifact(db, artifact_id, current_user)
    return ArtifactResponse(
        id=artifact.id,
        owner_id=artifact.owner_id,
        file_size_bytes=artifact.file_size_bytes,
        duration_seconds=artifact.duration_seconds,
        sample_rate=artifact.sample_rate,
        format=artifact.format,
        created_at=artifact.created_at,
    )


@router.get("/{artifact_id}/file")
async def get_artifact_audio_file(
    artifact_id: str,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream or download the audio artifact WAV file.
    Secured strictly via 'Authorization: Bearer <token>' header.
    Rejects query parameter authentication (CWE-598) with HTTP 400.
    Supports HTTP Range requests for in-browser audio seeking.
    """
    if token is not None:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Query Authentication Prohibited",
            detail="Passing authentication tokens in URL query strings is prohibited for security reasons (CWE-598). Use 'Authorization: Bearer <token>' header.",
            code="QUERY_AUTH_PROHIBITED",
        )

    artifact = await ArtifactService.get_artifact(db, artifact_id, current_user)
    file_path = Path(artifact.file_path)

    media_type = "audio/wav" if artifact.format.lower() == "wav" else "application/octet-stream"
    filename = f"speech-{artifact.id[:8]}.{artifact.format}"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
