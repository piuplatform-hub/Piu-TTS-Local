"""
Hardware Resource Concurrency Manager
Enforces strict slot limits (max 1 GPU, max 1 CPU) on local Windows host.
"""

import asyncio
from typing import Dict, Set


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

    async def can_acquire(self, resource_type: str) -> bool:
        async with self._lock:
            total_active = len(self._active_gpu_jobs) + len(self._active_cpu_jobs)
            if total_active >= self.max_global_slots:
                return False

            normalized = resource_type.lower()
            if normalized == "gpu":
                return len(self._active_gpu_jobs) < self.max_gpu_slots
            else:
                return len(self._active_cpu_jobs) < self.max_cpu_slots

    async def acquire(self, resource_type: str, job_id: str) -> bool:
        async with self._lock:
            total_active = len(self._active_gpu_jobs) + len(self._active_cpu_jobs)
            if total_active >= self.max_global_slots:
                return False

            normalized = resource_type.lower()
            if normalized == "gpu":
                if len(self._active_gpu_jobs) < self.max_gpu_slots:
                    self._active_gpu_jobs.add(job_id)
                    return True
                return False
            else:
                if len(self._active_cpu_jobs) < self.max_cpu_slots:
                    self._active_cpu_jobs.add(job_id)
                    return True
                return False

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
