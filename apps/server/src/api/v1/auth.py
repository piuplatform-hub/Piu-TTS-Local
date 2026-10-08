from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.auth import (
    AuthStatusResponse,
    BootstrapRequest,
    LoginRequest,
    UserCreateRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
    StorageUsageResponse,
)
from ...services.auth_service import AuthService, get_current_user, require_admin
from ...services.user_quota_service import UserQuotaService
from ...core.security import create_access_token
from ...core.errors import AppException

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
            storage_quota_mb=user.storage_quota_mb,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Local login endpoint exchanging credentials for a JWT session token.
    Protected by application-level rate limiting and brute force defense.
    """
    # Bound IP extraction: Only trust direct socket peer host, no arbitrary X-Forwarded-For
    client_ip = request.client.host if request.client and request.client.host else "127.0.0.1"
    user = await AuthService.authenticate_user(db, req.username, req.password, ip_address=client_ip)
    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
            storage_quota_mb=user.storage_quota_mb,
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
        storage_quota_mb=current_user.storage_quota_mb,
    )


@router.post("/change-password")
async def change_user_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows the authenticated user to securely update their own password.
    """
    await AuthService.change_password(db, current_user, req.old_password, req.new_password)
    return {"message": "Password changed successfully."}


@router.get("/storage", response_model=StorageUsageResponse)
async def get_storage_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current user's cumulative disk storage usage and remaining quota.
    """
    usage = await UserQuotaService.get_user_storage_usage(db, current_user)
    return StorageUsageResponse(
        used_bytes=usage["used_bytes"],
        used_mb=usage["used_mb"],
        quota_mb=usage["quota_mb"],
        percent_used=usage["percent_used"],
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_account(
    req: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin-only endpoint to provision user accounts (editor or viewer).
    """
    if current_user.role != "admin":
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Admin Role Required",
            detail="Only administrators can create user accounts.",
            code="FORBIDDEN_USER_CREATION",
        )
    user = await AuthService.create_user(db, req, current_user)
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
        storage_quota_mb=user.storage_quota_mb,
    )

