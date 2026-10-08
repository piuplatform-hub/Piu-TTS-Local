"""
Pydantic Schemas for Audio Artifacts
"""

from datetime import datetime
from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    id: str
    owner_id: str
    file_size_bytes: int
    duration_seconds: float
    sample_rate: int
    format: str
    created_at: datetime
