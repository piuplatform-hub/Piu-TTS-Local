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


async def run_standalone_runner(
    poll_interval: float = 0.5,
    lease_seconds: int = 30,
    worker_id: str | None = None,
):
    pid = os.getpid()
    effective_worker_id = worker_id or f"runner-{pid}"

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
        logger.info("Standalone Runner terminated cleanly.")


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
