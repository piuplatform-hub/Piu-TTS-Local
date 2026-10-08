"""
AI Voice Studio — Headless Application Core Entrypoint (FastAPI)
"""

from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from . import database
from .core.errors import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from .core.security import get_or_create_bootstrap_token
from .services.auth_service import AuthService
from .services.engine_service import EngineService
from .supervisor.supervisor import supervisor
from .supervisor.scheduler import scheduler
from .api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB schema
    await database.init_db()

    workspace_root = Path(__file__).resolve().parents[3]

    async with database.AsyncSessionLocal() as session:
        auth_status = await AuthService.get_status(session)
        if auth_status["needs_onboarding"]:
            token = get_or_create_bootstrap_token()
            print("\n" + "=" * 65)
            print(" [AI VOICE STUDIO] FIRST-RUN ONBOARDING REQUIRED")
            print(f" One-Time Local Bootstrap Token: {token}")
            print(f" Web UI: http://{settings.HOST}:{settings.PORT}")
            print("=" * 65 + "\n")

        # Discover & spawn registered local inference engines
        await EngineService.discover_and_register_engines(session, workspace_root)

    # Start Durable Job Scheduler daemon
    await scheduler.start()

    yield

    # Shutdown: Stop scheduler and cleanly terminate worker child processes
    print("\nShutting down AI Voice Studio scheduler and worker processes...")
    await scheduler.stop()
    await supervisor.stop_all()


app = FastAPI(
    title="AI Voice Studio",
    description="Professional Local-First Modular AI Speech Synthesis Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Exception Handlers (RFC 9457 Problem Details)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# CORS Middleware (Loopback & Dev UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Router
app.include_router(api_v1_router)

# Mount Frontend Static Assets (if built)
dist_dir = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = dist_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        "apps.server.src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
