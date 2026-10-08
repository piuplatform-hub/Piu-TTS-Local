"""
Reference Audio Asset Entity Model
Stores uploaded audio samples for zero-shot voice cloning with consent tracking and per-user ownership.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from ..database import Base


class ReferenceAssetRecord(Base):
    __tablename__ = "reference_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, default=0.0, nullable=False)
    sample_rate = Column(Integer, default=24000, nullable=False)
    channels = Column(Integer, default=1, nullable=False)
    format = Column(String(10), default="wav", nullable=False)
    voice_use_consent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
