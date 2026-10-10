"""
Pydantic Schemas for Engine Registry & Capability Discovery
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PresetVoiceSchema(BaseModel):
    id: str
    name: str
    language: str
    gender: str = "unspecified"


class ParameterDefinitionSchema(BaseModel):
    name: str
    type: str  # "number", "integer", "boolean", "string"
    min: Optional[float] = None
    max: Optional[float] = None
    default: Any = None
    step: Optional[float] = None
    category: str = "native"  # "native" | "dsp"
    label: str
    description: str
    enum: Optional[List[str]] = None


class VoicePresetSchema(BaseModel):
    id: str
    label: str
    description: str
    values: Dict[str, Any]


class EngineCapabilityDetailResponse(BaseModel):
    engine_id: str
    name: str
    version: str
    installed: bool = True
    status: str = "ready"  # "ready" | "unloaded" | "error" | "not_installed"
    device_target: str = "cpu"
    capabilities: List[str] = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)
    default_sample_rate: int = 48000
    parameters: List[ParameterDefinitionSchema] = Field(default_factory=list)
    presets: List[VoicePresetSchema] = Field(default_factory=list)
    preset_voices: List[PresetVoiceSchema] = Field(default_factory=list)
    description: Optional[str] = None


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
