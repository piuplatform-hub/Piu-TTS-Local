"""
Process Supervisor Fault-Isolation & Crash Recovery Tests
"""

from pathlib import Path
import pytest
from apps.server.src.supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest


@pytest.mark.asyncio
async def test_worker_crash_isolation_and_restart():
    workspace_root = Path(__file__).resolve().parents[2]
    manifest_path = workspace_root / "engines" / "mock" / "engine.manifest.json"
    manifest = EngineManifest.from_file(str(manifest_path))

    # 1. Start worker initially
    worker = await supervisor.start_worker(manifest=manifest, workspace_root=workspace_root)
    initial_port = worker.port
    assert worker.is_alive() is True

    # 2. Simulate worker sudden crash/kill
    worker.process.kill()
    worker.process.wait()
    assert worker.is_alive() is False

    # 3. Supervisor detects dead worker and get_client returns None (fail-safe)
    client_after_crash = supervisor.get_client("mock-tts")
    assert client_after_crash is None

    # 4. Supervisor restarts worker cleanly on a fresh port
    restarted_worker = await supervisor.start_worker(manifest=manifest, workspace_root=workspace_root)
    assert restarted_worker.is_alive() is True
    assert restarted_worker.client is not None

    # 5. Relaunched worker responds to health check
    health = await restarted_worker.client.get_health()
    assert health.status == "healthy"

    # Teardown
    await supervisor.stop_all()
