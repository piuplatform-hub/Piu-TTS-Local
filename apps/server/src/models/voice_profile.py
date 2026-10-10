"""
Voice Profile Entity Model
Stores reusable voice profiles with reference audio and default parameters,
isolated per user in application storage.
"""

from datetime import datetime, timezone
import json
from typing import Dict, Any, Optional
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from ..database import Base


class VoiceProfileRecord(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    engine_id: Mapped[str] = mapped_column(String(50), nullable=False, default="vieneu-tts")
    reference_asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("reference_assets.id", ondelete="CASCADE"), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    reference_asset = relationship("ReferenceAssetRecord")
    user = relationship("User")

    @property
    def parameters(self) -> Dict[str, Any]:
        try:
            return json.loads(self.parameters_json)
        except Exception:
            return {}

    @parameters.setter
    def parameters(self, val: Dict[str, Any]):
        self.parameters_json = json.dumps(val or {}, ensure_ascii=False)
