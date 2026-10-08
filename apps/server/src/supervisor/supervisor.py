"""
Engine Worker Process Supervisor
Spawns, authenticates, monitors and gracefully terminates isolated child workers.
"""

import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from engine_sdk.client import EngineWorkerClient
from engine_sdk.manifest import EngineManifest


class WorkerInstance:
    def __init__(self, engine_id: str, manifest: EngineManifest, process: subprocess.Popen, port: int, auth_token: str):
        self.engine_id = engine_id
        self.manifest = manifest
        self.process = process
        self.port = port
        self.auth_token = auth_token
        self.client = EngineWorkerClient(base_url=f"http://127.0.0.1:{port}", auth_token=auth_token)

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def terminate(self):
        if self.is_alive():
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()


class ProcessSupervisor:
    def __init__(self):
        self._workers: Dict[str, WorkerInstance] = {}

    async def start_worker(self, manifest: EngineManifest, workspace_root: Path) -> WorkerInstance:
        engine_id = manifest.engine_id
        if engine_id in self._workers and self._workers[engine_id].is_alive():
            return self._workers[engine_id]

        entrypoint = workspace_root / manifest.runtime.entrypoint
        if not entrypoint.exists():
            raise FileNotFoundError(f"Worker entrypoint does not exist: {entrypoint}")

        python_bin = sys.executable
        if manifest.runtime.virtualenv_path:
            venv_python = workspace_root / manifest.runtime.virtualenv_path / "Scripts" / "python.exe"
            if venv_python.exists():
                python_bin = str(venv_python)

        auth_token = secrets.token_hex(24)

        # Launch worker child process on loopback ephemeral port
        proc = subprocess.Popen(
            [python_bin, str(entrypoint), "--port", "0", "--auth-token", auth_token, "--parent-pid", str(os.getpid())],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(workspace_root),
        )

        port: Optional[int] = None
        for _ in range(60):
            line = proc.stdout.readline()
            if line.startswith("PORT:"):
                port = int(line.strip().split(":")[1])
                break
            await asyncio.sleep(0.05)

        if port is None or proc.poll() is not None:
            err = proc.stderr.read() if proc.stderr else "Unknown error"
            raise RuntimeError(f"Failed to start worker for engine {engine_id}: {err}")

        instance = WorkerInstance(
            engine_id=engine_id,
            manifest=manifest,
            process=proc,
            port=port,
            auth_token=auth_token,
        )

        # Health check probe
        health = await instance.client.get_health()
        if health.status != "healthy":
            instance.terminate()
            raise RuntimeError(f"Worker {engine_id} health probe failed: {health}")

        self._workers[engine_id] = instance
        return instance

    def get_client(self, engine_id: str) -> Optional[EngineWorkerClient]:
        worker = self._workers.get(engine_id)
        if worker and worker.is_alive():
            return worker.client
        return None

    def shutdown_all(self):
        for worker in self._workers.values():
            worker.terminate()
        self._workers.clear()

    async def stop_all(self):
        self.shutdown_all()



# Global singleton supervisor
supervisor = ProcessSupervisor()
