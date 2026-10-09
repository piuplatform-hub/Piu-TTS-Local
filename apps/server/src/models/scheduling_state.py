"""
User Scheduling State Data Model
Tracks per-user dispatch history per resource type (CPU/GPU) for starvation-free Fair-Share scheduling.
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UserSchedulingStateRecord(Base):
    __tablename__ = "user_scheduling_states"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(10), primary_key=True)  # 'cpu' or 'gpu'
    last_dispatched_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)
    dispatched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
