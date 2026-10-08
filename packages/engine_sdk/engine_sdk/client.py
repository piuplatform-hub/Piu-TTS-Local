"""
Engine Worker Client for AI Voice Studio Core Supervisor
Communicates with isolated worker subprocesses over loopback HTTP.
"""

from typing import Optional
import httpx

from .protocol import (
    HealthResponse,
    InfoResponse,
    SynthesisRequest,
    SynthesisResponse,
    ErrorResponse,
)


class WorkerError(RuntimeError):
    def __init__(self, code: str, detail: str, status_code: int):
        super().__init__(f"Worker Error [{code}]: {detail}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class EngineWorkerClient:
    def __init__(self, base_url: str, auth_token: str, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._headers = {"X-Worker-Token": auth_token}

    async def get_health(self) -> HealthResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/health", headers=self._headers)
            resp.raise_for_status()
            return HealthResponse(**resp.json())

    async def get_info(self) -> InfoResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/info", headers=self._headers)
            resp.raise_for_status()
            return InfoResponse(**resp.json())

    async def synthesize(self, request: SynthesisRequest, timeout: Optional[float] = None) -> bytes:
        effective_timeout = timeout or self.timeout
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            resp = await client.post(
                f"{self.base_url}/synthesize",
                headers=self._headers,
                json=request.model_dump(),
            )
            if resp.status_code != 200:
                err_response = None
                try:
                    err_data = resp.json()
                    err_response = ErrorResponse(**err_data)
                except Exception:
                    pass

                if err_response:
                    raise WorkerError(
                        code=err_response.code,
                        detail=err_response.detail,
                        status_code=resp.status_code,
                    )
                resp.raise_for_status()
            return resp.content

    async def unload(self) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/unload", headers=self._headers)
            resp.raise_for_status()
            return resp.json()
