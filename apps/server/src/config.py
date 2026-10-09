"""
AI Voice Studio — Application Configuration & Environment Settings
"""

import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Network binding (Localhost only for Phase 1)
    HOST: str = "127.0.0.1"
    PORT: int = 8765

    # Security
    SECRET_KEY: str = "ai-voice-studio-dev-secret-key-change-in-production-32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Configurable data directory (Default proposed: D:\AIVoiceStudioData or ./data)
    STUDIO_DATA_DIR: str = "D:\\AIVoiceStudioData"

    # Database URL
    DATABASE_URL: str = ""

    # Hardware & Concurrency
    MAX_CONCURRENT_CPU_JOBS: int = 1
    ENABLE_GPU_INFERENCE: bool = False

    # Scheduler Execution Mode (True: runs inside FastAPI lifespan; False: external runner.py)
    EMBEDDED_SCHEDULER: bool = True

    # Audio DSP & FFmpeg binary path (configurable via STUDIO_FFMPEG_PATH env)
    STUDIO_FFMPEG_PATH: str = ""

    # Milestone 5A: Multi-User Quotas, Resource Fairness & Multi-Dimensional Login Protection
    USER_STORAGE_QUOTA_MB: int = 5120  # 5GB default candidate per user (0 = unlimited)
    MAX_OUTSTANDING_JOBS_PER_USER: int = 25  # Max queued + running jobs per user
    LOGIN_MAX_FAILED_ATTEMPTS_PAIR: int = 5  # Max consecutive failed attempts per (IP, username) pair
    LOGIN_MAX_FAILED_ATTEMPTS_USER: int = 10  # Max consecutive failed attempts per account across all IPs (distributed attack)
    LOGIN_MAX_FAILED_ATTEMPTS_IP: int = 20  # Max consecutive failed attempts per source IP across all usernames (credential spraying)
    LOGIN_LOCKOUT_WINDOW_MINUTES: int = 15  # Lockout observation window and backoff in minutes

    # Phase 5B-1: Reverse Proxy & Trusted Client Identity
    TRUST_FORWARDED_HEADERS: bool = True
    TRUSTED_PROXIES: list[str] = ["127.0.0.1", "::1"]
    UVICORN_PROXY_HEADERS: bool = False  # Explicitly disabled so Uvicorn does not mutate scope['client']
    UVICORN_FORWARDED_ALLOW_IPS: str = ""  # Disable Uvicorn default IP forwarding in favor of custom resolver
    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://127.0.0.1:9443",
        "https://localhost:9443",
    ]

    @field_validator("TRUSTED_PROXIES", "CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_list_from_env(cls, v):
        if isinstance(v, str):
            cleaned = v.strip()
            if cleaned.startswith("[") and cleaned.endswith("]"):
                import json
                try:
                    return json.loads(cleaned)
                except Exception:
                    pass
            return [x.strip() for x in cleaned.split(",") if x.strip()]
        return v

    def get_data_dir(self) -> Path:
        """
        Returns resolved data directory path. Creates subdirectories if they don't exist.
        Falls back safely to local './data' if target path is not writable.
        """
        path = Path(self.STUDIO_DATA_DIR)
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = path / ".write_test"
            test_file.touch()
            test_file.unlink()
            resolved = path
        except Exception:
            resolved = Path("./data").resolve()
            resolved.mkdir(parents=True, exist_ok=True)

        # Ensure standard subdirectories
        (resolved / "models").mkdir(parents=True, exist_ok=True)
        (resolved / "voices").mkdir(parents=True, exist_ok=True)
        (resolved / "artifacts" / "temp").mkdir(parents=True, exist_ok=True)
        (resolved / "artifacts" / "exports").mkdir(parents=True, exist_ok=True)
        (resolved / "backups").mkdir(parents=True, exist_ok=True)
        return resolved

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        data_dir = self.get_data_dir()
        db_path = (data_dir / "studio.db").as_posix()
        return f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
