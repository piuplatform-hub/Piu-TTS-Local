"""
Security & Authentication Core: Argon2id Hashing, JWT Sessions & One-Time Bootstrap Token
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from ..config import settings

# Initialize Argon2id hasher with secure parameters
hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against an Argon2id hash."""
    try:
        return hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decodes and validates a JWT token. Raises exceptions on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_bootstrap_token_file() -> Path:
    return settings.get_data_dir() / ".bootstrap_token"


def get_or_create_bootstrap_token() -> str:
    """
    Returns existing bootstrap token or generates a new one-time token.
    The token is stored in the data directory and also logged for the local admin.
    """
    token_file = get_bootstrap_token_file()
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception:
            pass

    token = secrets.token_hex(24)  # 48-char secure random hex
    token_file.write_text(token, encoding="utf-8")
    return token


def consume_bootstrap_token(provided_token: str) -> bool:
    """
    Verifies the one-time bootstrap token and deletes it immediately upon success.
    Returns True if valid, False otherwise.
    """
    token_file = get_bootstrap_token_file()
    if not token_file.exists():
        return False

    try:
        stored_token = token_file.read_text(encoding="utf-8").strip()
        # Constant-time comparison
        if secrets.compare_digest(stored_token, provided_token.strip()):
            # Delete token file atomically
            token_file.unlink(missing_ok=True)
            return True
    except Exception:
        pass
    return False
