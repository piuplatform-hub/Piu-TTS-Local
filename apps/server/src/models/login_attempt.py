"""
Login Attempt Audit Model (Brute Force & Password Spraying Protection)
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from ..database import Base


class LoginAttemptRecord(Base):
    __tablename__ = "login_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ip_address = Column(String(45), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    attempted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    success = Column(Boolean, default=False, nullable=False)
