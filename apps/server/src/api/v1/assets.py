"""
Reference Audio Assets API Endpoints (v1)
Secure upload, management, and retrieval of audio references for voice cloning.
"""

from typing import List
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.asset import ReferenceAssetResponse, ReferenceAssetUploadResponse
from ...services.auth_service import get_current_user, require_editor
from ...services.asset_service import AssetService
from ...services.user_quota_service import UserQuotaService

router = APIRouter(prefix="/assets", tags=["Reference Assets"])


@router.post("/reference-audio", response_model=ReferenceAssetUploadResponse, status_code=201)
async def upload_reference_audio(
    file: UploadFile = File(...),
    voice_use_consent: bool = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """
    Securely upload a reference WAV audio file for zero-shot voice cloning.
    Validates audio format, duration (0.5s - 30s), enforces explicit consent,
    enforces user storage quota, and isolates storage under user-specific directories.
    Requires editor or admin role.
    """
    file_bytes = await file.read()
    filename = file.filename or "reference.wav"

    # Transactionally reserve storage capacity before persisting audio asset
    res_rec = await UserQuotaService.reserve_capacity(
        db=db,
        user=current_user.id,
        estimated_bytes=len(file_bytes),
        reservation_type="reference_asset",
        timeout_seconds=300,
    )

    try:
        record = await AssetService.upload_reference_audio(
            db=db,
            user=current_user,
            file_bytes=file_bytes,
            original_filename=filename,
            voice_use_consent=voice_use_consent,
        )
        await UserQuotaService.commit_reservation(db, res_rec.id, record.file_size_bytes)
        await db.commit()
    except Exception:
        await UserQuotaService.release_reservation(db, res_rec.id)
        await db.commit()
        raise

    asset_resp = ReferenceAssetResponse(
        id=record.id,
        user_id=record.user_id,
        filename=record.filename,
        file_size_bytes=record.file_size_bytes,
        duration_seconds=record.duration_seconds,
        sample_rate=record.sample_rate,
        channels=record.channels,
        format=record.format,
        voice_use_consent=record.voice_use_consent,
        created_at=record.created_at,
    )

    return ReferenceAssetUploadResponse(
        asset_id=record.id,
        message="Reference audio uploaded and verified successfully.",
        asset=asset_resp,
    )


@router.get("/reference-audio", response_model=List[ReferenceAssetResponse])
async def list_reference_audios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all authorized reference audio assets belonging to the current user.
    """
    records = await AssetService.list_user_reference_assets(db, current_user)
    return [
        ReferenceAssetResponse(
            id=r.id,
            user_id=r.user_id,
            filename=r.filename,
            file_size_bytes=r.file_size_bytes,
            duration_seconds=r.duration_seconds,
            sample_rate=r.sample_rate,
            channels=r.channels,
            format=r.format,
            voice_use_consent=r.voice_use_consent,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/reference-audio/{asset_id}", response_model=ReferenceAssetResponse)
async def get_reference_audio(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get metadata for a specific reference audio asset.
    Strictly enforces per-user ownership authorization.
    """
    record = await AssetService.get_reference_asset(db, asset_id, current_user)
    return ReferenceAssetResponse(
        id=record.id,
        user_id=record.user_id,
        filename=record.filename,
        file_size_bytes=record.file_size_bytes,
        duration_seconds=record.duration_seconds,
        sample_rate=record.sample_rate,
        channels=record.channels,
        format=record.format,
        voice_use_consent=record.voice_use_consent,
        created_at=record.created_at,
    )


@router.delete("/reference-audio/{asset_id}")
async def delete_reference_audio(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """
    Delete a reference audio asset and remove physical audio bytes from disk.
    Requires editor or admin role.
    """
    await AssetService.delete_reference_asset(db, asset_id, current_user)
    return {"message": "Reference audio deleted successfully.", "asset_id": asset_id}
