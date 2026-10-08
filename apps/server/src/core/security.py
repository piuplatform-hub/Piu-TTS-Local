"""
Security & Authentication Core: Argon2id Hashing, JWT Sessions & One-Time Bootstrap Token
Hardened for Zero-Trust Localhost, TTL Expiration, and Atomic Race-Condition Safety.
"""

import json
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from ..config import settings

# Initialize Argon2id hasher with secure parameters (RFC 9106 compliant)
hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Bootstrap Token Time-To-Live: 15 minutes
BOOTSTRAP_TOKEN_TTL_SECONDS = 900


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
    Returns existing active bootstrap token or generates a new one-time token with TTL.
    Structured storage contains token, created_at, and expires_at.
    """
    token_file = get_bootstrap_token_file()
    now = time.time()

    if token_file.exists():
        try:
            content = token_file.read_text(encoding="utf-8").strip()
            # Try parsing JSON format
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    token = data.get("token")
                    expires_at = data.get("expires_at", 0)
                    if token and now < expires_at:
                        return token
            except json.JSONDecodeError:
                # Handle legacy plain-text token: expire it safely and issue structured one
                pass
            # Token expired or corrupt: remove and regenerate
            token_file.unlink(missing_ok=True)
        except Exception:
            token_file.unlink(missing_ok=True)

    token = secrets.token_hex(24)  # 48-character cryptographically secure hex
    payload = {
        "token": token,
        "created_at": now,
        "expires_at": now + BOOTSTRAP_TOKEN_TTL_SECONDS,
    }
    token_file.write_text(json.dumps(payload), encoding="utf-8")
    return token


def consume_bootstrap_token(provided_token: str) -> bool:
    """
    Atomically verifies and consumes the one-time bootstrap token.
    Uses atomic filesystem rename to prevent concurrent race conditions.
    Validates token value and TTL expiration.
    Returns True if valid and consumed, False otherwise.
    """
    token_file = get_bootstrap_token_file()
    if not token_file.exists() or not provided_token:
        return False

    # Atomic rename target to claim exclusive consumption ownership
    claim_file = token_file.with_name(f".bootstrap_token.consumed.{uuid.uuid4().hex}")

    try:
        # Atomic rename at OS level: only ONE concurrent thread or process can succeed
        os.replace(token_file, claim_file)
    except (FileNotFoundError, OSError):
        # Already claimed or missing
        return False

    valid = False
    expired = False
    try:
        content = claim_file.read_text(encoding="utf-8").strip()
        stored_token = ""
        expires_at = 0.0

        try:
            data = json.loads(content)
            if isinstance(data, dict):
                stored_token = data.get("token", "")
                expires_at = float(data.get("expires_at", 0.0))
        except json.JSONDecodeError:
            stored_token = content
            expires_at = time.time() + 60.0  # legacy fallback

        now = time.time()
        if expires_at > 0.0 and now > expires_at:
            expired = True
        elif stored_token and secrets.compare_digest(stored_token, provided_token.strip()):
            valid = True
    except Exception:
        pass
    finally:
        if valid or expired:
            # Consumed or expired: permanently destroy claim file
            claim_file.unlink(missing_ok=True)
        else:
            # Unmatched token: restore file so valid admin can complete onboarding
            try:
                os.replace(claim_file, token_file)
            except Exception:
                claim_file.unlink(missing_ok=True)

    return valid
