"""
System Health API Endpoints (v1)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def system_health(db: AsyncSession = Depends(get_db)):
    """
    Core system health status and database connectivity check.
    """
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "version": "1.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
