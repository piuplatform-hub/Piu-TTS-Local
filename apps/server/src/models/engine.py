"""
Engine Registry Entity Model
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, JSON, DateTime, Boolean
from ..database import Base


class EngineRecord(Base):
    __tablename__ = "engines"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    approval_status = Column(String(20), default="approved", nullable=False)  # pending, approved, disabled
    device_target = Column(String(20), default="cpu", nullable=False)
    capabilities = Column(JSON, default=list, nullable=False)
    manifest_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
