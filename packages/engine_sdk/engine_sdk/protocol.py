"""
Engine Adapter HTTP Protocol & Error Schemas (RFC 9457 compliant)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkerState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    INFERRING = "inferring"
    UNLOADING = "unloading"
    ERROR = "error"


class PresetVoice(BaseModel):
    id: str
    name: str
    language: str
    gender: Optional[str] = "unspecified"
    description: Optional[str] = ""


class SynthesisRequest(BaseModel):
    job_id: str
    text: str = Field(..., min_length=1)
    language: str = Field("vi")
    voice_id: Optional[str] = None
    speed: float = Field(1.0, ge=0.25, le=4.0)
    sample_rate: Optional[int] = Field(None, ge=8000, le=96000)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SynthesisResponse(BaseModel):
    job_id: str
    duration_seconds: float
    sample_rate: int
    format: str = "wav"


class HealthResponse(BaseModel):
    status: str = "healthy"
    engine_id: str
    state: WorkerState = WorkerState.READY
    device: str = "cpu"
    memory_mb: Optional[int] = 0
    vram_mb: Optional[int] = 0


class InfoResponse(BaseModel):
    engine_id: str
    name: str
    version: str
    capabilities: List[str]
    supported_languages: List[str]
    preset_voices: List[PresetVoice] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    type: str = "https://ai-voice-studio.local/errors/worker-error"
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    code: str
    retryable: bool = False
    backoff_seconds: Optional[int] = None
