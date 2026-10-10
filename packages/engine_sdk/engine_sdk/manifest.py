"""
Engine Manifest Schema & Validation (v1.0)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class CapabilityEnum(str, Enum):
    TEXT_TO_SPEECH = "text_to_speech"
    VOICE_CLONING = "voice_cloning"
    SPEAKER_SELECTION = "speaker_selection"
    STREAMING_AUDIO = "streaming_audio"
    MULTILINGUAL_SYNTHESIS = "multilingual_synthesis"
    EMOTION_CONTROL = "emotion_control"
    ADVANCED_VOICE_CONTROLS = "advanced_voice_controls"


class EngineRuntime(BaseModel):
    entrypoint: str = Field(..., description="Path to worker entrypoint script (e.g. worker.py)")
    python_version_min: str = Field("3.10", description="Minimum supported Python version")
    python_version_max: str = Field("3.12", description="Maximum supported Python version")
    virtualenv_path: Optional[str] = Field(None, description="Optional path to engine-specific .venv")


class HardwareProfile(BaseModel):
    supported_devices: List[str] = Field(default_factory=lambda: ["cpu"])
    default_device: str = Field("cpu")
    estimated_vram_mb: int = Field(0, ge=0)
    estimated_ram_mb: int = Field(512, ge=0)


class EngineManifest(BaseModel):
    manifest_version: str = Field("1.0", description="Manifest format version")
    engine_id: str = Field(..., pattern=r"^[a-z0-9_-]+$", description="Unique engine identifier")
    name: str = Field(..., min_length=2, max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+.*$")
    author: str = Field(..., min_length=2)
    license: str = Field("Apache-2.0")
    description: str = Field("")
    capabilities: List[CapabilityEnum] = Field(..., min_length=1)
    supported_languages: List[str] = Field(..., min_length=1)
    default_sample_rate: int = Field(44100, ge=8000, le=96000)
    runtime: EngineRuntime
    hardware_profile: HardwareProfile = Field(default_factory=HardwareProfile)
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)

    def has_capability(self, cap: CapabilityEnum) -> bool:
        return cap in self.capabilities

    @classmethod
    def from_file(cls, path: str) -> "EngineManifest":
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
