"""
Authentication & Authorization Service (Headless Core)
"""

from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.user import User
from ..schemas.auth import BootstrapRequest
from ..core.security import hash_password, verify_password, decode_access_token, consume_bootstrap_token
from ..core.errors import AppException
from ..database import get_db

security_scheme = HTTPBearer(auto_error=False)


class AuthService:
    @staticmethod
    async def get_status(db: AsyncSession) -> dict:
        stmt = select(func.count(User.id))
        result = await db.execute(stmt)
        count = result.scalar() or 0
        return {
            "needs_onboarding": count == 0,
            "total_users": count,
        }

    @staticmethod
    async def bootstrap_admin(db: AsyncSession, req: BootstrapRequest) -> User:
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

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
        stmt = select(User).where(User.username == username.strip())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
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

        return user


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
    except Exception as e:
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
