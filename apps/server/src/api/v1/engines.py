"""
Engine Registry & Status API Endpoints (v1)
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...schemas.engine import EngineDetailResponse
from ...services.auth_service import get_current_user
from ...services.engine_service import EngineService
from ...supervisor.supervisor import supervisor
from ...core.errors import AppException

router = APIRouter(prefix="/engines", tags=["Engines"])


@router.get("", response_model=List[EngineDetailResponse])
async def list_registered_engines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all approved AI inference engines, their device targets,
    supported languages, and available preset voices.
    """
    return await EngineService.list_engines(db)


@router.get("/{engine_id}/health")
async def check_engine_health(
    engine_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check the loopback health status of an engine's worker process.
    """
    client = supervisor.get_client(engine_id)
    if not client:
        raise AppException(
            status_code=404,
            title="Engine Not Running",
            detail=f"Engine '{engine_id}' worker is not running or not found.",
            code="ENGINE_WORKER_NOT_RUNNING",
        )

    try:
        health = await client.check_health()
        return health.model_dump()
    except Exception as exc:
        raise AppException(
            status_code=503,
            title="Engine Worker Unhealthy",
            detail=f"Failed to communicate with engine worker: {exc}",
            code="ENGINE_WORKER_UNHEALTHY",
        )
