"""
Voice Profiles API Endpoints (v1)
Provides management for reusable, user-isolated cloned voice profiles.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.voice_profile import (
    VoiceProfileCreate,
    VoiceProfileUpdate,
    VoiceProfileResponse,
)
from ...services.auth_service import get_current_user, require_editor
from ...services.voice_profile_service import VoiceProfileService

router = APIRouter(prefix="/voices/profiles", tags=["Voice Profiles"])


@router.post("", response_model=VoiceProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_profile(
    req: VoiceProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """
    Create a reusable voice profile linked to an approved reference audio asset.
    Persists profile in user-isolated storage and SQLite.
    """
    profile = await VoiceProfileService.create_profile(db, current_user, req)
    return VoiceProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        description=profile.description,
        engine_id=profile.engine_id,
        reference_asset_id=profile.reference_asset_id,
        parameters=profile.parameters,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=List[VoiceProfileResponse])
async def list_voice_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all voice profiles owned by the current user.
    """
    profiles = await VoiceProfileService.list_profiles(db, current_user)
    return [
        VoiceProfileResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            description=p.description,
            engine_id=p.engine_id,
            reference_asset_id=p.reference_asset_id,
            parameters=p.parameters,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in profiles
    ]


@router.get("/{profile_id}", response_model=VoiceProfileResponse)
async def get_voice_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific voice profile by ID. Enforces ownership authorization.
    """
    profile = await VoiceProfileService.get_profile(db, profile_id, current_user)
    return VoiceProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        description=profile.description,
        engine_id=profile.engine_id,
        reference_asset_id=profile.reference_asset_id,
        parameters=profile.parameters,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put("/{profile_id}", response_model=VoiceProfileResponse)
async def update_voice_profile(
    profile_id: str,
    req: VoiceProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """
    Update voice profile name, description, or default parameters.
    """
    profile = await VoiceProfileService.update_profile(db, profile_id, current_user, req)
    return VoiceProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        description=profile.description,
        engine_id=profile.engine_id,
        reference_asset_id=profile.reference_asset_id,
        parameters=profile.parameters,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.delete("/{profile_id}", status_code=status.HTTP_200_OK)
async def delete_voice_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    """
    Delete a voice profile and its on-disk metadata file.
    """
    await VoiceProfileService.delete_profile(db, profile_id, current_user)
    return {"message": "Voice profile deleted successfully.", "profile_id": profile_id}
