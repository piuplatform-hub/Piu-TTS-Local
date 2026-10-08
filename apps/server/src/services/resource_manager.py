"""
Hardware Resource Concurrency Manager
Enforces strict slot limits (max 1 GPU, max 1 CPU) on local Windows host.
Supports both database-backed multi-process synchronization and local in-memory lock coordination.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import database
from ..models.job import JobRecord
from .job_state_machine import JobState


class ResourceManager:
    def __init__(
        self,
        max_gpu_slots: int = 1,
        max_cpu_slots: int = 1,
        max_global_slots: int = 2,
    ):
        self.max_gpu_slots = max_gpu_slots
        self.max_cpu_slots = max_cpu_slots
        self.max_global_slots = max_global_slots

        self._active_gpu_jobs: Set[str] = set()
        self._active_cpu_jobs: Set[str] = set()
        self._lock = asyncio.Lock()

    async def get_db_active_counts(
        self,
        session: Optional[AsyncSession] = None,
        exclude_job_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Queries live unexpired active leases from SQLite to guarantee global cross-process slot enforcement.
        Optionally excludes a specific job_id (e.g., the job currently being claimed/transitioned).
        """
        now = datetime.now(timezone.utc)

        async def _query(s: AsyncSession) -> Dict[str, int]:
            conditions = [
                JobRecord.status.in_([JobState.PREPARING.value, JobState.RUNNING.value]),
                JobRecord.lease_expires_at > now,
            ]
            if exclude_job_id:
                conditions.append(JobRecord.id != exclude_job_id)

            stmt = (
                select(JobRecord.resource_type, func.count(JobRecord.id))
                .where(*conditions)
                .group_by(JobRecord.resource_type)
            )
            res = await s.execute(stmt)
            counts = {row[0]: row[1] for row in res.all()}
            gpu_active = counts.get("gpu", 0)
            cpu_active = counts.get("cpu", 0)
            return {
                "active_gpu": gpu_active,
                "active_cpu": cpu_active,
                "total_active": gpu_active + cpu_active,
            }

        if session is not None:
            return await _query(session)
        else:
            async with database.AsyncSessionLocal() as s:
                return await _query(s)

    async def can_acquire(
        self,
        resource_type: str,
        session: Optional[AsyncSession] = None,
        exclude_job_id: Optional[str] = None,
    ) -> bool:
        normalized = resource_type.lower()
        exclude_set = {exclude_job_id} if exclude_job_id else set()

        async with self._lock:
            # 1. Check local in-process tracking
            active_gpu_local = len(self._active_gpu_jobs - exclude_set)
            active_cpu_local = len(self._active_cpu_jobs - exclude_set)
            total_local = active_gpu_local + active_cpu_local

            if total_local >= self.max_global_slots:
                return False
            if normalized == "gpu" and active_gpu_local >= self.max_gpu_slots:
                return False
            if normalized != "gpu" and active_cpu_local >= self.max_cpu_slots:
                return False

        # 2. Check global database state across processes
        try:
            db_counts = await self.get_db_active_counts(session, exclude_job_id=exclude_job_id)
            if db_counts["total_active"] >= self.max_global_slots:
                return False
            if normalized == "gpu" and db_counts["active_gpu"] >= self.max_gpu_slots:
                return False
            if normalized != "gpu" and db_counts["active_cpu"] >= self.max_cpu_slots:
                return False
        except Exception:
            # Defensive fallback to in-memory accounting if DB query is unavailable
            pass

        return True

    async def acquire(
        self,
        resource_type: str,
        job_id: str,
        session: Optional[AsyncSession] = None,
    ) -> bool:
        normalized = resource_type.lower()
        if not await self.can_acquire(normalized, session, exclude_job_id=job_id):
            return False

        async with self._lock:
            if normalized == "gpu":
                self._active_gpu_jobs.add(job_id)
            else:
                self._active_cpu_jobs.add(job_id)
            return True

    async def release(self, resource_type: str, job_id: str) -> None:
        async with self._lock:
            normalized = resource_type.lower()
            if normalized == "gpu":
                self._active_gpu_jobs.discard(job_id)
            else:
                self._active_cpu_jobs.discard(job_id)

    async def release_all(self, job_id: str) -> None:
        async with self._lock:
            self._active_gpu_jobs.discard(job_id)
            self._active_cpu_jobs.discard(job_id)

    async def get_active_counts(self) -> Dict[str, int]:
        async with self._lock:
            return {
                "active_gpu": len(self._active_gpu_jobs),
                "max_gpu": self.max_gpu_slots,
                "active_cpu": len(self._active_cpu_jobs),
                "max_cpu": self.max_cpu_slots,
                "total_active": len(self._active_gpu_jobs) + len(self._active_cpu_jobs),
                "max_global": self.max_global_slots,
            }

    async def reset(self) -> None:
        async with self._lock:
            self._active_gpu_jobs.clear()
            self._active_cpu_jobs.clear()


# Global singleton instance
resource_manager = ResourceManager()
