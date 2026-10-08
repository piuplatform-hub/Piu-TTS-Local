"""
Project Export Data Model
Represents a rendered master audio export of a project (WAV / MP3).
"""

from datetime import datetime
import uuid

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ProjectExportRecord(Base):
    __tablename__ = "project_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # "wav" or "mp3"
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=48000)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    loudness_lufs: Mapped[float] = mapped_column(Float, nullable=True)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("ProjectRecord", back_populates="exports")
    user = relationship("User")
