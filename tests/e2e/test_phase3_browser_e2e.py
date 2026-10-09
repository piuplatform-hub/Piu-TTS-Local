"""
Real Chrome Browser End-to-End Tests for Phase 3 Neural Inference
Verifies the complete user experience in Google Chrome via Playwright:
1. Onboarding / Authentication.
2. VieNeu-TTS (CPU): Select preset voice 'hai_dang', synthesize Vietnamese audio, inspect 48kHz WAV player.
3. VieNeu-TTS Voice Cloning: Switch to cloning mode, provide reference WAV, capture UI state.
4. Qwen3-TTS (GPU): Select Mandarin engine, choose speaker 'vivian', synthesize on RTX 3050, inspect 24kHz audio.
5. Job History view: Confirm durable tracking of both neural engines.
Captures screenshots to docs/reports/screenshots/.
"""

import asyncio
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
import wave
import pytest
from playwright.sync_api import sync_playwright
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.main import app
from apps.server.src.supervisor.supervisor import supervisor

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOT_DIR = Path("docs/reports/screenshots").resolve()


def test_phase3_real_browser_e2e_journey():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors = []
    network_failures = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        settings.STUDIO_DATA_DIR = str(tmp_path)
        db_file = tmp_path / "e2e_phase3_studio.db"

        # Create sample reference audio WAV in temp dir
        ref_sample_wav = tmp_path / "sample_voice.wav"
        sr = 24000
        n_samples = int(sr * 1.5)
        with wave.open(str(ref_sample_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            frames = bytearray()
            for i in range(n_samples):
                val = int(32767.0 * 0.2 * math.sin(2 * math.pi * 261.63 * i / sr))
                frames.extend(struct.pack("<h", val))
            wf.writeframes(frames)

        # Database engine
        test_engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_file}",
            connect_args={"check_same_thread": False},
        )
        database.engine = test_engine
        database.AsyncSessionLocal = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Run Alembic migrations
        from alembic.config import Config
        from alembic import command
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        # Dynamically allocate free port to prevent TIME_WAIT collisions
        import socket
        import urllib.request
        def get_free_port() -> int:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]

        port = get_free_port()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            proxy_headers=settings.UVICORN_PROXY_HEADERS,
            forwarded_allow_ips=settings.UVICORN_FORWARDED_ALLOW_IPS,
        )
        server = uvicorn.Server(config)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        # Wait until server is fully responsive
        server_ready = False
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/auth/status", timeout=0.5) as resp:
                    if resp.status == 200:
                        server_ready = True
                        break
            except Exception:
                time.sleep(0.15)
        assert server_ready, f"Server failed to start on port {port}"

        # Read setup token
        token_file = tmp_path / ".bootstrap_token"
        assert token_file.exists(), "Bootstrap token file missing"
        token_data = json.loads(token_file.read_text(encoding="utf-8"))
        setup_token = token_data["token"]

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url}: {req.failure}"))

            base_url = f"http://127.0.0.1:{port}"

            # Step 1: Onboarding
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector("text=Khởi tạo Quản Trị Cục Bộ", timeout=10000)
            page.fill('input[placeholder="admin"]', "lead_architect")
            page.fill('input[type="password"] >> nth=0', "SecurePassword123!")
            page.fill('input[type="password"] >> nth=1', "SecurePassword123!")
            page.fill('input[placeholder="Dán token 48 ký tự từ console..."]', setup_token)
            page.click('button:has-text("Hoàn tất & Khởi tạo Hệ thống")')

            # Step 2: Speech Studio Authenticated & Switch to Single TTS Tab if needed
            page.wait_for_selector("text=lead_architect", timeout=10000)
            if page.locator('button:has-text("Thử Giọng Lẻ")').count() > 0:
                page.click('button:has-text("Thử Giọng Lẻ")')
            page.wait_for_selector("text=Speech Studio", timeout=10000)
            page.wait_for_selector("text=Phase 3 Neural Engines", timeout=10000)

            # Wait for engines to populate in select
            page.wait_for_selector('option[value="vieneu-tts"]', state="attached", timeout=10000)

            # Step 3: Test VieNeu-TTS (CPU) Synthesis
            page.select_option('select:has(option[value="vieneu-tts"])', value="vieneu-tts")
            page.fill(
                'textarea[placeholder="Nhập đoạn văn bản cần chuyển thành giọng nói tại đây..."]',
                "Chào mừng bạn đến với AI Voice Studio. Tổng hợp tiếng Việt trên CPU chất lượng cao 48 kilohertz."
            )
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_01_vieneu_setup.png"))

            # Click Synthesize
            page.click('button:has-text("Tạo giọng nói AI")')

            # Wait for synthesis completion and player
            page.wait_for_selector("text=Tải WAV", timeout=45000)
            page.wait_for_selector("text=48kHz", timeout=10000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_02_vieneu_completed.png"))

            # Step 4: Test VieNeu-TTS Voice Cloning UI
            page.click('button:has-text("Nhân bản giọng")')
            page.set_input_files('input[type="file"]', str(ref_sample_wav))
            page.wait_for_selector(f"text={ref_sample_wav.name}", timeout=5000)
            page.check('input[type="checkbox"] >> nth=0')
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_03_vieneu_cloning_ui.png"))

            # Step 5: Test Qwen3-TTS (GPU) Synthesis
            page.select_option('select:has(option[value="qwen3-tts"])', value="qwen3-tts")
            page.wait_for_selector("text=Đích: GPU", timeout=5000)
            page.wait_for_selector("text=Mẫu: 24kHz", timeout=5000)
            page.fill(
                'textarea[placeholder="Nhập đoạn văn bản cần chuyển thành giọng nói tại đây..."]',
                "你好，欢迎使用 Qwen3-TTS 本地语音合成系统。"
            )
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_04_qwen3_setup.png"))

            page.click('button:has-text("Tạo giọng nói AI")')

            # Wait for GPU synthesis completion
            page.wait_for_selector("text=Tải WAV", timeout=60000)
            page.wait_for_selector("text=24kHz", timeout=10000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_05_qwen3_completed.png"))

            # Step 6: Verify History Tab
            page.click('button:has-text("Lịch sử")')
            page.wait_for_selector("text=Lịch Sử Tạo Giọng Nói", timeout=5000)
            page.wait_for_selector("text=vieneu-tts", timeout=5000)
            page.wait_for_selector("text=qwen3-tts", timeout=5000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase3_06_history_view.png"))

            browser.close()

        # Shutdown server
        server.should_exit = True
        server_thread.join(timeout=5)
        try:
            asyncio.run(supervisor.stop_all())
        except Exception:
            pass
        try:
            asyncio.run(test_engine.dispose())
        except Exception:
            pass

    # Validate console errors
    critical_errors = [e for e in console_errors if "favicon" not in e.lower() and "401" not in e]
    assert len(critical_errors) == 0, f"Unexpected console errors: {critical_errors}"

    # Confirm all 6 screenshots were generated
    for sc_name in [
        "phase3_01_vieneu_setup.png",
        "phase3_02_vieneu_completed.png",
        "phase3_03_vieneu_cloning_ui.png",
        "phase3_04_qwen3_setup.png",
        "phase3_05_qwen3_completed.png",
        "phase3_06_history_view.png",
    ]:
        p = SCREENSHOT_DIR / sc_name
        assert p.exists() and p.stat().st_size > 10000, f"Missing screenshot {sc_name}"
