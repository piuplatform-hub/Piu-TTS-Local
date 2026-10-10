"""
API v1 Router Aggregator
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .engines import router as engines_router
from .jobs import router as jobs_router
from .artifacts import router as artifacts_router
from .assets import router as assets_router
from .projects import router as projects_router
from .health import router as health_router
from .voice_profiles import router as voice_profiles_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(engines_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(artifacts_router)
api_v1_router.include_router(assets_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(voice_profiles_router)
