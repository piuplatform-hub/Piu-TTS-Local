"""
Inference Job Entity Model (SQLite Persistent Queue Tracking)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, UniqueConstraint
from ..database import Base


class JobRecord(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_idempotency_key"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    engine_id = Column(String(50), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=True)
    job_type = Column(String(20), default="tts", nullable=False)
    status = Column(String(20), default="queued", nullable=False, index=True)  # queued, preparing, running, completed, failed, cancelled
    progress_percent = Column(Integer, default=0, nullable=False)
    worker_id = Column(String(50), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    payload_data = Column(JSON, default=dict, nullable=False)
    error_details = Column(JSON, nullable=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=True)
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
