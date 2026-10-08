"""
Pytest Fixtures for AI Voice Studio Integration Tests
"""

import asyncio
from pathlib import Path
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.main import app
from apps.server.src.supervisor.supervisor import supervisor
from apps.server.src.services.engine_service import EngineService
from engine_sdk.manifest import EngineManifest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_env():
    """
    Sets up an isolated temporary data directory and test SQLite database for each test.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        settings.STUDIO_DATA_DIR = str(tmp_path)
        db_path = tmp_path / "test_studio.db"

        # Re-bind database engine and sessionmaker
        test_engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        database.engine = test_engine
        database.AsyncSessionLocal = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Initialize schema tables
        await database.init_db()

        yield {
            "tmp_path": tmp_path,
            "db_path": db_path,
        }

        # Cleanup
        await test_engine.dispose()


@pytest.fixture(scope="function")
async def client(test_env):
    """
    Provides an AsyncClient bound to the FastAPI app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="function")
async def running_mock_engine(test_env):
    """
    Ensures the Mock Engine worker is registered and running during test.
    """
    workspace_root = Path(__file__).resolve().parents[1]
    mock_manifest_path = workspace_root / "engines" / "mock" / "engine.manifest.json"
    manifest = EngineManifest.from_file(str(mock_manifest_path))

    await supervisor.start_worker(manifest=manifest, workspace_root=workspace_root)

    # Sync into test DB
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(session, workspace_root)

    yield manifest

    await supervisor.stop_all()
