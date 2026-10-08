"""
Authentication & Onboarding API Endpoints (v1)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.auth import (
    AuthStatusResponse,
    BootstrapRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from ...services.auth_service import AuthService, get_current_user
from ...core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(db: AsyncSession = Depends(get_db)):
    """
    Check if the system has been initialized with an administrator.
    If true, the UI redirects to onboarding.
    """
    data = await AuthService.get_status(db)
    return AuthStatusResponse(**data)


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_initial_admin(
    req: BootstrapRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    First-Run Bootstrap: Atomically creates the primary admin user
    using the one-time local setup token generated on startup.
    """
    user = await AuthService.bootstrap_admin(db, req)
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Local login endpoint exchanging credentials for a JWT session token.
    """
    user = await AuthService.authenticate_user(db, req.username, req.password)
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the authenticated user's profile and permissions.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at,
    )
