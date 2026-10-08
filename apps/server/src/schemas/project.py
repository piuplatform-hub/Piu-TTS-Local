"""
Project, Character, Segment, and Export Pydantic Schemas
Provides strict validation for Phase 4 Studio domain entities.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# CHARACTER SCHEMAS
# -------------------------------------------------------------
class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    avatar_color: str = Field(default="#10b981", pattern="^#[0-9a-fA-F]{6}$")
    engine_id: str = Field(..., min_length=1, max_length=50)
    voice_id: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="vi", pattern="^(vi|zh|en)$")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0)


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    engine_id: Optional[str] = Field(None, min_length=1, max_length=50)
    voice_id: Optional[str] = Field(None, min_length=1, max_length=100)
    language: Optional[str] = Field(None, pattern="^(vi|zh|en)$")
    parameters: Optional[Dict[str, Any]] = None
    sort_order: Optional[int] = None


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    avatar_color: str
    engine_id: str
    voice_id: str
    language: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------
# SEGMENT SCHEMAS
# -------------------------------------------------------------
class SegmentRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    segment_id: str
    revision_number: int
    text: str
    engine_id: str
    voice_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    artifact_id: str
    job_id: Optional[str] = None
    duration_seconds: float
    created_at: datetime


class SegmentCreate(BaseModel):
    character_id: Optional[str] = None
    sequence_order: int = Field(default=0)
    text: str = Field(..., min_length=1)
    language: str = Field(default="vi", pattern="^(vi|zh|en)$")
    engine_id: str = Field(default="vieneu-tts")
    voice_id: str = Field(default="hai_dang")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    pause_after_ms: int = Field(default=300, ge=0, le=5000)


class SegmentUpdate(BaseModel):
    character_id: Optional[str] = None
    sequence_order: Optional[int] = None
    text: Optional[str] = Field(None, min_length=1)
    language: Optional[str] = Field(None, pattern="^(vi|zh|en)$")
    engine_id: Optional[str] = None
    voice_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    pause_after_ms: Optional[int] = Field(None, ge=0, le=5000)


class SegmentSyncItem(BaseModel):
    id: Optional[str] = None  # None for new segment
    character_id: Optional[str] = None
    sequence_order: int
    text: str
    language: str = "vi"
    engine_id: str = "vieneu-tts"
    voice_id: str = "hai_dang"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    pause_after_ms: int = 300


class SegmentBulkSyncRequest(BaseModel):
    expected_project_version: int
    segments: List[SegmentSyncItem]


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    character_id: Optional[str] = None
    sequence_order: int
    text: str
    language: str
    engine_id: str
    voice_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    pause_after_ms: int
    status: str
    active_artifact_id: Optional[str] = None
    last_job_id: Optional[str] = None
    text_hash: str
    version: int
    revisions: List[SegmentRevisionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------
# PROJECT EXPORT SCHEMAS
# -------------------------------------------------------------
class MasterExportRequest(BaseModel):
    format: Literal["wav", "mp3"] = "wav"
    sample_rate: int = Field(default=48000, description="Target sample rate (e.g. 48000, 44100, 24000)")
    normalize_loudness: bool = Field(default=True, description="Apply EBU R128 loudness normalization")
    target_lufs: float = Field(default=-16.0, description="Target integrated LUFS (-16 for podcast/web, -23 for broadcast)")


class ProjectExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    user_id: str
    format: str
    sample_rate: int
    file_path: str
    file_size_bytes: int
    duration_seconds: float
    sha256_checksum: str
    loudness_lufs: Optional[float] = None
    segment_count: int
    created_at: datetime


# -------------------------------------------------------------
# PROJECT SCHEMAS
# -------------------------------------------------------------
class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: Literal["narration", "dialogue"] = "narration"
    settings: Dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    expected_version: Optional[int] = Field(None, description="Expected version for optimistic concurrency check")


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    project_type: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    version: int
    segment_count: int = 0
    completed_segment_count: int = 0
    total_audio_duration_s: float = 0.0
    created_at: datetime
    updated_at: datetime


class ProjectDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    project_type: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    version: int
    characters: List[CharacterResponse] = Field(default_factory=list)
    segments: List[SegmentResponse] = Field(default_factory=list)
    exports: List[ProjectExportResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------
# TEXT SEGMENTATION SCHEMAS
# -------------------------------------------------------------
class TextSegmentRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: Literal["vi", "zh", "en"] = "vi"
    max_chars_per_segment: int = Field(default=220, ge=40, le=400)
    default_engine_id: Optional[str] = None
    default_voice_id: Optional[str] = None


class TextSegmentItem(BaseModel):
    index: int
    text: str
    char_count: int


class TextSegmentResponse(BaseModel):
    language: str
    total_chars: int
    segment_count: int
    segments: List[TextSegmentItem]
