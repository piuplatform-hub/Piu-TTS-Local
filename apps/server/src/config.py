"""
AI Voice Studio — Application Configuration & Environment Settings
"""

import os
from pathlib import Path
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
