"""
Pydantic Schemas for TTS Jobs (Durable Queue & Resilience)
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TTSJobSubmitRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    engine_id: str = Field("mock-tts")
    language: str = Field("vi")
    voice_id: Optional[str] = None
    speed: float = Field(1.0, ge=0.25, le=4.0)
    idempotency_key: Optional[str] = Field(None, max_length=100)
    priority: int = Field(0, ge=-10, le=10)


class JobResponse(BaseModel):
    id: str
    user_id: str
    engine_id: str
    job_type: str
    status: str
    progress_percent: int
    priority: int = 0
    resource_type: str = "cpu"
    attempt_count: int = 0
    max_retries: int = 3
    waiting_reason: Optional[str] = None
    artifact_id: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
