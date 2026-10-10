"""
Voice Profile Schemas (v1)
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class VoiceProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the cloned voice profile")
    reference_asset_id: str = Field(..., description="ID of the uploaded and verified reference audio asset")
    engine_id: str = Field(default="vieneu-tts", description="Target inference engine (e.g. vieneu-tts)")
    description: Optional[str] = Field(default=None, max_length=255, description="Optional description or persona notes")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Default sampling and DSP parameters")


class VoiceProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=255)
    parameters: Optional[Dict[str, Any]] = None


class VoiceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    engine_id: str
    reference_asset_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
