"""
Durable Job Event Service & SSE Broadcaster
Persists events to SQLite job_events table and streams to SSE subscribers with Last-Event-ID replay.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import database
from ..models.job import JobEventRecord


class JobEventService:
    def __init__(self):
        # Maps job_id -> set of asyncio.Queue for live streaming subscribers
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def emit_event(
        self,
        db: AsyncSession,
        job_id: str,
        event_type: str,
        data: dict,
    ) -> JobEventRecord:
        """
        Durably saves the event into the database and broadcasts to active SSE listeners.
        """
        event_rec = JobEventRecord(
            job_id=job_id,
            event_type=event_type,
            data=data,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event_rec)
        await db.flush()

        event_payload = {
            "id": event_rec.id,
            "job_id": job_id,
            "event_type": event_type,
            "data": data,
            "created_at": event_rec.created_at.isoformat() if event_rec.created_at else None,
        }

        # Broadcast to in-memory listeners
        async with self._lock:
            queues = self._subscribers.get(job_id, set()).copy()
            for q in queues:
                try:
                    q.put_nowait(event_payload)
                except asyncio.QueueFull:
                    pass

        return event_rec

    async def subscribe(
        self,
        job_id: str,
        last_event_id: Optional[int] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Yields replayed historical events if last_event_id is provided,
        then streams real-time events until terminal event or disconnect.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # 1. Register queue
        async with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add(queue)

        try:
            # 2. Replay historical events from DB
            highest_replayed_id = last_event_id or 0
            async with database.AsyncSessionLocal() as session:
                query = select(JobEventRecord).where(JobEventRecord.job_id == job_id)
                if last_event_id is not None:
                    query = query.where(JobEventRecord.id > last_event_id)
                query = query.order_by(JobEventRecord.id.asc())
                res = await session.execute(query)
                records = res.scalars().all()

                for r in records:
                    highest_replayed_id = max(highest_replayed_id, r.id)
                    yield {
                        "id": r.id,
                        "job_id": r.job_id,
                        "event_type": r.event_type,
                        "data": r.data,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    if r.event_type in ("completed", "failed", "cancelled"):
                        return

            # 3. Stream live events
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    # Deduplicate in case event was already replayed
                    if event["id"] and event["id"] <= highest_replayed_id:
                        continue

                    highest_replayed_id = max(highest_replayed_id, event["id"] or 0)
                    yield event

                    if event.get("event_type") in ("completed", "failed", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    # Keep-alive ping
                    yield {
                        "id": None,
                        "job_id": job_id,
                        "event_type": "ping",
                        "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                    }
        finally:
            # Clean up queue subscription
            async with self._lock:
                if job_id in self._subscribers:
                    self._subscribers[job_id].discard(queue)
                    if not self._subscribers[job_id]:
                        del self._subscribers[job_id]


# Global singleton instance
event_service = JobEventService()
