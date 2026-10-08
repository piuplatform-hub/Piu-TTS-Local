"""
Script Segment & Revision Data Models
Represents individual text lines/paragraphs and their non-destructive rendered audio revisions.
"""

from datetime import datetime
import json
import uuid
from typing import Dict, Any, List

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ScriptSegmentRecord(Base):
    __tablename__ = "script_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True, index=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="vi")
    engine_id: Mapped[str] = mapped_column(String(50), ForeignKey("engines.id"), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    pause_after_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    
    # Status: draft, queued, rendering, completed, failed, stale
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    active_artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    last_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("ProjectRecord", back_populates="segments")
    character = relationship("CharacterRecord", back_populates="segments")
    active_artifact = relationship("ArtifactRecord", foreign_keys=[active_artifact_id])
    last_job = relationship("JobRecord", foreign_keys=[last_job_id])
    revisions = relationship("SegmentRevisionRecord", back_populates="segment", cascade="all, delete-orphan", lazy="selectin", order_by="SegmentRevisionRecord.revision_number.desc()")

    @property
    def parameters(self) -> Dict[str, Any]:
        try:
            return json.loads(self.parameters_json)
        except Exception:
            return {}

    @parameters.setter
    def parameters(self, val: Dict[str, Any]):
        self.parameters_json = json.dumps(val or {}, ensure_ascii=False)


class SegmentRevisionRecord(Base):
    __tablename__ = "segment_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id: Mapped[str] = mapped_column(String(36), ForeignKey("script_segments.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    engine_id: Mapped[str] = mapped_column(String(50), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    segment = relationship("ScriptSegmentRecord", back_populates="revisions")
    artifact = relationship("ArtifactRecord")
    job = relationship("JobRecord")

    @property
    def parameters(self) -> Dict[str, Any]:
        try:
            return json.loads(self.parameters_json)
        except Exception:
            return {}

    @parameters.setter
    def parameters(self, val: Dict[str, Any]):
        self.parameters_json = json.dumps(val or {}, ensure_ascii=False)
