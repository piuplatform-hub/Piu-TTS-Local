"""
Storage Reservation Data Model
Supports transactional Capacity Reservation, Finalization, and Release for concurrency-safe quota enforcement.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class StorageReservationRecord(Base):
    __tablename__ = "storage_reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    reservation_type: Mapped[str] = mapped_column(String(30), nullable=False)  # 'speech_job', 'master_export', 'reference_asset'
    reserved_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)  # 'ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED'
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
