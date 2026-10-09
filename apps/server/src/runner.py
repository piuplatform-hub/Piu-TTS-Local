"""
AI Voice Studio — Standalone Durable Job Runner Process
Entrypoint: python -m apps.server.src.runner

Runs the DurableJobScheduler daemon in an independent OS process,
completely decoupled from the FastAPI HTTP web server process.
Discovers local AI inference engines, manages worker subprocesses via Windows Job Objects,
and continuously claims and executes durable jobs using database-backed leases.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import signal
import sys

from . import database
from .config import settings
from .services.engine_service import EngineService
from .supervisor.scheduler import DurableJobScheduler
from .supervisor.supervisor import supervisor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("studio.runner")


class RunnerProcessLock:
    """
    Exclusive OS-level file lock ensuring only a single Standalone Runner
    instance executes at any given time.
    """
    def __init__(self, lock_path: Path | str):
        self.lock_path = Path(lock_path)
        self._file = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._file = open(self.lock_path, "a+b")
            self._file.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._file.seek(0)
            self._file.truncate()
            self._file.write(f"pid={os.getpid()}\nstarted={datetime.now(timezone.utc).isoformat()}\n".encode("utf-8"))
            self._file.flush()
            return True
        except (OSError, IOError, PermissionError):
            if self._file:
                try:
                    self._file.close()
                except Exception:
                    pass
                self._file = None
            return False

    def release(self):
        if self._file:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self._file.seek(0)
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
                self._file.close()
            except Exception:
                pass
            self._file = None
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass


async def run_standalone_runner(
    poll_interval: float = 0.5,
    lease_seconds: int = 30,
    worker_id: str | None = None,
):
    pid = os.getpid()
    effective_worker_id = worker_id or f"runner-{pid}"

    # Enforce process uniqueness via exclusive lockfile
    lock_file = settings.get_data_dir() / ".runner.lock"
    runner_lock = RunnerProcessLock(lock_file)
    if not runner_lock.acquire():
        logger.error("=" * 65)
        logger.error("STARTUP ABORTED: ANOTHER STANDALONE RUNNER IS ALREADY ACTIVE!")
        logger.error(f"Lockfile currently held at: {lock_file}")
        logger.error("Only one runner instance may execute simultaneously to preserve engine & queue isolation.")
        logger.error("=" * 65)
        return False

    logger.info("=" * 65)
    logger.info(f"AI VOICE STUDIO — STANDALONE RUNNER INITIALIZING (PID: {pid})")
    logger.info(f"Worker ID: {effective_worker_id}")
    logger.info(f"Poll Interval: {poll_interval}s | Lease Duration: {lease_seconds}s")
    logger.info("=" * 65)

    # 1. Initialize Database Schema
    await database.init_db()

    # 2. Discover engines and spawn worker subprocesses
    workspace_root = Path(__file__).resolve().parents[3]
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(
            db=session,
            workspace_root=workspace_root,
            spawn_workers=True,
        )

    # 3. Instantiate and start dedicated scheduler
    runner_scheduler = DurableJobScheduler(
        poll_interval_seconds=poll_interval,
        lease_seconds=lease_seconds,
        worker_id=effective_worker_id,
    )
    await runner_scheduler.start()

    logger.info(f"Standalone Runner active and listening for queued jobs...")

    # 4. Graceful shutdown handler
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal. Initiating graceful shutdown...")
        stop_event.set()

    # Register OS signal handlers
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)
    else:
        # Windows signal handling
        signal.signal(signal.SIGINT, lambda s, f: handle_signal())
        signal.signal(signal.SIGTERM, lambda s, f: handle_signal())

    try:
        await stop_event.wait()
    finally:
        logger.info("Stopping scheduler and draining running tasks...")
        await runner_scheduler.stop()
        logger.info("Terminating supervised engine workers...")
        await supervisor.stop_all()
        await database.engine.dispose()
        runner_lock.release()
        logger.info("Standalone Runner terminated cleanly.")
    return True


def main():
    parser = argparse.ArgumentParser(description="AI Voice Studio Standalone Job Runner")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds for queue checking (default: 0.5)",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=30,
        help="Duration of lease in seconds acquired on claimed jobs (default: 30)",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Unique identifier for this runner instance in the database (default: runner-{pid})",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_standalone_runner(
                poll_interval=args.poll_interval,
                lease_seconds=args.lease_seconds,
                worker_id=args.worker_id,
            )
        )
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
