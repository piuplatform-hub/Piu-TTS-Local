"""
Engine Worker Process Supervisor
Spawns, authenticates, monitors and gracefully terminates isolated child workers.
Features Windows Job Object integration for bulletproof child process-tree termination.
"""

import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Any

from engine_sdk.client import EngineWorkerClient
from engine_sdk.manifest import EngineManifest


def _setup_windows_job_object(process: subprocess.Popen) -> Optional[Any]:
    """
    On Windows, binds the child process to a Job Object configured with
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000).
    Guarantees that child and any grandchildren processes terminate if the
    parent crashes or closes the job handle.
    """
    if os.name != "nt":
        return None

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))

        proc_handle = getattr(process, "_handle", None)
        if proc_handle:
            kernel32.AssignProcessToJobObject(job, int(proc_handle))
        return job
    except Exception:
        # Graceful fallback: supervisor will use standard terminate/kill
        return None


class WorkerInstance:
    def __init__(
        self,
        engine_id: str,
        manifest: EngineManifest,
        process: subprocess.Popen,
        port: int,
        auth_token: str,
        job_handle: Optional[Any] = None,
    ):
        self.engine_id = engine_id
        self.manifest = manifest
        self.process = process
        self.port = port
        self.auth_token = auth_token
        self.job_handle = job_handle
        self.client = EngineWorkerClient(base_url=f"http://127.0.0.1:{port}", auth_token=auth_token)

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def terminate(self):
        if self.is_alive():
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception:
                    pass

        # Close Windows Job Object handle if active
        if self.job_handle and os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.job_handle)
                self.job_handle = None
            except Exception:
                pass


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

        job_handle = _setup_windows_job_object(proc)

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
            job_handle=job_handle,
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
