"""
Inference Job Entity Models (Durable SQLite Queue Tracking & SSE Events)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from ..database import Base


class JobRecord(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_idempotency_key"),
        Index("ix_jobs_queue_order", "status", "priority", "queued_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    engine_id = Column(String(50), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=True)
    job_type = Column(String(20), default="tts", nullable=False)
    status = Column(String(20), default="queued", nullable=False, index=True)  # queued, preparing, running, completed, failed, cancelled
    progress_percent = Column(Integer, default=0, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    resource_type = Column(String(10), default="cpu", nullable=False)  # cpu, gpu
    attempt_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    current_attempt_id = Column(String(36), nullable=True)
    locked_by = Column(String(100), nullable=True)
    worker_id = Column(String(50), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    waiting_reason = Column(String(255), nullable=True)
    payload_data = Column(JSON, default=dict, nullable=False)
    error_details = Column(JSON, nullable=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=True)
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class JobEventRecord(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        Index("ix_job_events_job_id_id", "job_id", "id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
