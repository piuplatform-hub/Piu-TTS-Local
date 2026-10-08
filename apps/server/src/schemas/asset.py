"""
Pydantic Schemas for Reference Audio Assets
"""

from datetime import datetime
from pydantic import BaseModel, Field


class ReferenceAssetResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    file_size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    format: str
    voice_use_consent: bool
    created_at: datetime


class ReferenceAssetUploadResponse(BaseModel):
    asset_id: str
    message: str
    asset: ReferenceAssetResponse
