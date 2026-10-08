"""
Pydantic Schemas for Engine Registry
"""

from typing import Any, Dict, List
from pydantic import BaseModel


class PresetVoiceSchema(BaseModel):
    id: str
    name: str
    language: str
    gender: str = "unspecified"


class EngineDetailResponse(BaseModel):
    id: str
    name: str
    version: str
    approval_status: str
    device_target: str
    capabilities: List[str]
    supported_languages: List[str]
    preset_voices: List[PresetVoiceSchema] = []
    parameters_schema: Dict[str, Any] = {}
