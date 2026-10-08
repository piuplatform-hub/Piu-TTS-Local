"""
Authentication & Authorization Service (Headless Core)
"""

import asyncio
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.user import User
from ..schemas.auth import BootstrapRequest, UserCreateRequest
from ..core.security import hash_password, verify_password, decode_access_token, consume_bootstrap_token
from ..core.errors import AppException
from ..database import get_db

security_scheme = HTTPBearer(auto_error=False)


class AuthService:
    _bootstrap_lock = asyncio.Lock()

    @staticmethod
    async def get_status(db: AsyncSession) -> dict:
        stmt = select(func.count(User.id))
        result = await db.execute(stmt)
        count = result.scalar() or 0
        return {
            "needs_onboarding": count == 0,
            "total_users": count,
        }

    @classmethod
    async def bootstrap_admin(cls, db: AsyncSession, req: BootstrapRequest) -> User:
        async with cls._bootstrap_lock:
            # 1. Enforce atomic single-admin initialization
            stmt = select(func.count(User.id))
            result = await db.execute(stmt)
            user_count = result.scalar() or 0

            if user_count > 0:
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    title="System Already Initialized",
                    detail="An administrator account already exists. Onboarding is closed.",
                    code="ALREADY_INITIALIZED",
                )

            # 2. Verify and atomically consume the one-time local setup token
            if not consume_bootstrap_token(req.setup_token):
                raise AppException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    title="Invalid Setup Token",
                    detail="The provided setup token is invalid, expired, or has already been consumed.",
                    code="INVALID_SETUP_TOKEN",
                )

            # 3. Create initial Admin with Argon2id hash
            try:
                hashed = hash_password(req.password)
                admin_user = User(
                    username=req.username.strip(),
                    password_hash=hashed,
                    role="admin",
                    is_active=True,
                )
                db.add(admin_user)
                await db.commit()
                await db.refresh(admin_user)
                return admin_user
            except Exception as e:
                await db.rollback()
                raise AppException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    title="Initialization Failed",
                    detail=f"Failed to record administrator user: {e}",
                    code="BOOTSTRAP_DB_ERROR",
                )

    @staticmethod
    async def create_user(db: AsyncSession, req: UserCreateRequest, current_user: User) -> User:
        if current_user.role != "admin":
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="Admin Privileges Required",
                detail="Only administrators can provision new users.",
                code="FORBIDDEN_USER_CREATION",
            )

        stmt = select(User).where(User.username == req.username.strip())
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                title="Username Already Exists",
                detail=f"User '{req.username}' already exists.",
                code="USERNAME_EXISTS",
            )

        new_user = User(
            username=req.username.strip(),
            password_hash=hash_password(req.password),
            role=req.role,
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username: str,
        password: str,
        ip_address: str = "127.0.0.1",
    ) -> User:
        from .login_protection_service import LoginProtectionService

        # 1. Rate Limiting Check (Brute-Force & Password Spraying Protection)
        is_limited, retry_after = await LoginProtectionService.check_rate_limit(db, ip_address, username)
        if is_limited:
            raise AppException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                title="Too Many Login Attempts",
                detail=f"Too many failed login attempts. Please try again after {retry_after} seconds.",
                code="TOO_MANY_LOGIN_ATTEMPTS",
                extra={"retry_after": retry_after},
            )

        stmt = select(User).where(User.username == username.strip())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        # Non-enumerating credential verification
        if not user or not verify_password(password, user.password_hash):
            await LoginProtectionService.record_attempt(db, ip_address, username, success=False)
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Invalid Credentials",
                detail="Incorrect username or password.",
                code="INVALID_CREDENTIALS",
            )

        if not user.is_active:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="Account Disabled",
                detail="This user account has been deactivated.",
                code="ACCOUNT_DISABLED",
            )

        # Login success -> reset failed attempts
        await LoginProtectionService.record_attempt(db, ip_address, username, success=True)
        return user

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user: User,
        old_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Invalid Current Password",
                detail="Current password is incorrect.",
                code="INVALID_OLD_PASSWORD",
            )

        if len(new_password) < 8:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Weak Password",
                detail="New password must be at least 8 characters long.",
                code="PASSWORD_TOO_SHORT",
            )

        user.password_hash = hash_password(new_password)
        await db.commit()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Authentication Required",
            detail="Missing Bearer access token in Authorization header.",
            code="UNAUTHORIZED",
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token missing subject claim")
    except Exception:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Invalid or Expired Token",
            detail="The access token is invalid or has expired.",
            code="INVALID_TOKEN",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="User Inactive",
            detail="User not found or deactivated.",
            code="USER_INACTIVE",
        )

    return user


async def require_editor(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces editor or administrator role for creative synthesis and project mutations.
    Rejects viewer role with 403 Forbidden.
    """
    if current_user.role not in ("admin", "editor"):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Editor Privilege Required",
            detail="Editor or administrator role is required for this action.",
            code="FORBIDDEN_INSUFFICIENT_ROLE",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces exclusive administrator role for system and user management.
    """
    if current_user.role != "admin":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Admin Privilege Required",
            detail="Administrator role is required for this action.",
            code="FORBIDDEN_ADMIN_REQUIRED",
        )
    return current_user


async def get_user_from_token_str(token_str: str, db: AsyncSession) -> User:
    """Validates raw token string (used for EventSource SSE query parameter auth)."""
    try:
        payload = decode_access_token(token_str)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token missing subject claim")
    except Exception:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Invalid or Expired Token",
            detail="The access token is invalid or has expired.",
            code="INVALID_TOKEN",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="User Inactive",
            detail="User not found or deactivated.",
            code="USER_INACTIVE",
        )

    return user

