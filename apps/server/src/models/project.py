"""
Project Data Model
Represents a persistent audio creation project (Narration or Dialogue).
Supports Optimistic Concurrency Control via version field.
"""

from datetime import datetime
import json
import uuid
from typing import Dict, Any, List

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, default="narration")  # "narration" or "dialogue"
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    characters = relationship("CharacterRecord", back_populates="project", cascade="all, delete-orphan", lazy="selectin", order_by="CharacterRecord.sort_order")
    segments = relationship("ScriptSegmentRecord", back_populates="project", cascade="all, delete-orphan", lazy="selectin", order_by="ScriptSegmentRecord.sequence_order")
    exports = relationship("ProjectExportRecord", back_populates="project", cascade="all, delete-orphan", lazy="selectin", order_by="ProjectExportRecord.created_at.desc()")

    @property
    def settings(self) -> Dict[str, Any]:
        try:
            return json.loads(self.settings_json)
        except Exception:
            return {}

    @settings.setter
    def settings(self, val: Dict[str, Any]):
        self.settings_json = json.dumps(val or {}, ensure_ascii=False)
