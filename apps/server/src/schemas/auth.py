"""
Pydantic Schemas for Authentication & Onboarding
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AuthStatusResponse(BaseModel):
    needs_onboarding: bool
    total_users: int


class BootstrapRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    setup_token: str = Field(..., min_length=16, description="One-time local setup secret from console or data directory")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
