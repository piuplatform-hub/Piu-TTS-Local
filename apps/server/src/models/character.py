"""
Character / Voice Persona Data Model
Represents an assigned speaker persona within a Dialogue project.
"""

from datetime import datetime
import json
import uuid
from typing import Dict, Any

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class CharacterRecord(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#10b981")
    engine_id: Mapped[str] = mapped_column(String(50), ForeignKey("engines.id"), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="vi")
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("ProjectRecord", back_populates="characters")
    segments = relationship("ScriptSegmentRecord", back_populates="character")

    @property
    def parameters(self) -> Dict[str, Any]:
        try:
            return json.loads(self.parameters_json)
        except Exception:
            return {}

    @parameters.setter
    def parameters(self, val: Dict[str, Any]):
        self.parameters_json = json.dumps(val or {}, ensure_ascii=False)
