"""
Fast CI Browser E2E Test for Phase 4 Master Audio Export & Authenticated Browser Download
Verifies:
1. Admin onboarding and project creation in Chrome via Playwright.
2. Segment generation and valid audio rendering state reconciliation.
3. Master Audio Export (DSP) trigger from UI modal (WAV and MP3).
4. Browser native file download interception via Playwright page.expect_download().
5. Verification of downloaded audio binary (headers, sample rate, file size, duration).
6. Export history persistence and re-download capability.
7. Verification of browser authentication (?token= parameter) and cross-user isolation.
Captures authentic screenshot: docs/reports/screenshots/phase4_06_browser_download_verified.png
"""

import json
import math
import os
from pathlib import Path
import struct
import tempfile
import threading
import time
import urllib.request
import urllib.error
import wave
import pytest
from playwright.sync_api import sync_playwright
import uvicorn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from alembic.config import Config
from alembic import command

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.main import app
from apps.server.src.models.user import User
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.core.security import create_access_token, hash_password

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOT_DIR = Path("docs/reports/screenshots").resolve()


def generate_valid_wav(file_path: Path, duration_s: float = 1.0, sample_rate: int = 48000):
    """Generates a synthetically valid 16-bit PCM mono WAV file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_s * sample_rate)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        pcm_bytes = bytearray()
        for i in range(num_samples):
            val = int(2800.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            pcm_bytes.extend(struct.pack("<h", val))
        wf.writeframes(pcm_bytes)


def test_phase4_real_browser_master_export_and_download():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors = []
    network_failures = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        settings.STUDIO_DATA_DIR = str(tmp_path)
        db_file = tmp_path / "e2e_phase4_export_dl.db"

        # Initialize SQLite database engine
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
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        # Dynamically allocate free port to prevent TIME_WAIT collisions
        import socket
        def get_free_port() -> int:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]

        port = get_free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
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

        # Read setup bootstrap token
        token_file = tmp_path / ".bootstrap_token"
        assert token_file.exists(), "Bootstrap token file missing"
        token_data = json.loads(token_file.read_text(encoding="utf-8"))
        setup_token = token_data["token"]

        browser_launch_args = {}
        if Path(CHROME_PATH).is_file():
            browser_launch_args["executable_path"] = CHROME_PATH

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                **browser_launch_args,
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                accept_downloads=True,
            )
            page = context.new_page()

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url}: {req.failure}"))

            base_url = f"http://127.0.0.1:{port}"

            # Step 1: Onboard admin user
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector("text=Khởi tạo Quản Trị Cục Bộ", timeout=10000)
            page.fill('input[placeholder="admin"]', "studio_qa_lead")
            page.fill('input[type="password"] >> nth=0', "StudioPass123!")
            page.fill('input[type="password"] >> nth=1', "StudioPass123!")
            page.fill('input[placeholder="Dán token 48 ký tự từ console..."]', setup_token)
            page.click('button:has-text("Hoàn tất & Khởi tạo Hệ thống")')

            # Step 2: Confirm navigation to Projects Workspace
            page.wait_for_selector("text=Không Gian Làm Việc Dự Án (Workstation)", timeout=10000)

            # Step 3: Create Narration Project
            page.click('button:has-text("Tạo Dự Án Mới")')
            page.wait_for_selector("text=Tạo Dự Án Audio Studio Mới", timeout=5000)
            page.fill('input[placeholder="Ví dụ: Audio Book Chương 1 - Truyện Kiều"]', "Master Audio E2E Showcase")
            page.click('button:has-text("Tạo Dự Án Ngay")')

            # Step 4: Verify inside Speech Studio
            page.wait_for_selector("text=Master Audio E2E Showcase", timeout=10000)
            page.wait_for_selector("text=Phân Đoạn Văn Bản", timeout=10000)

            # Step 5: Automatically segment text into segments
            page.click('button:has-text("Phân Đoạn Văn Bản")')
            page.wait_for_selector("text=Tự Động Phân Đoạn Văn Bản Dài", timeout=5000)
            page.fill(
                'textarea[placeholder="Dán toàn bộ văn bản vào đây. Hệ thống sẽ tự động phân tách theo ranh giới ngữ nghĩa và dấu kết thúc câu..."]',
                "Phân đoạn một: Giọng đọc truyền cảm tự nhiên của AI Voice Studio. "
                "Phân đoạn hai: Âm thanh chất lượng phòng thu chuẩn DSP EBU R128."
            )
            page.click('button:has-text("Xem trước kết quả phân đoạn")')
            page.wait_for_selector("text=Đã phân tích:", timeout=5000)
            page.click('button:has-text("Áp Dụng Vào Sách Nói")')

            # Wait for segments to appear in UI
            page.wait_for_selector("text=Phân đoạn một: Giọng đọc truyền cảm", timeout=10000)

            # Step 6: Verify export button is initially disabled because segments are in draft status
            page.click('button:has-text("Xuất Bản Master DSP")')
            page.wait_for_selector("text=Xuất Bản Âm Thanh Master (DSP)", timeout=5000)
            page.wait_for_selector("text=Dự án chưa sẵn sàng để xuất bản Master", timeout=5000)
            # Export button must be disabled
            export_btn = page.locator('button:has-text("Bắt Đầu Ghép Nối & Xuất Bản Master")')
            assert export_btn.is_disabled(), "Export button should be disabled when segments are draft"
            page.click('button:has-text("Đóng")')

            # Step 7: Simulate completed audio synthesis for both segments
            # Generate valid audio artifacts and mark segments completed in DB
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = 'studio_qa_lead'")
            user_row = cursor.fetchone()
            assert user_row is not None, "studio_qa_lead user not found in DB"
            user_id = user_row[0]

            # Seed Bob as a secondary user for cross-user security verification
            cursor.execute(
                """INSERT OR IGNORE INTO users (id, username, password_hash, role, is_active, created_at)
                   VALUES ('user_bob_403', 'author_bob', 'dummy_hash', 'editor', 1, datetime('now'))"""
            )

            cursor.execute("SELECT id FROM script_segments ORDER BY sequence_order")
            seg_rows = cursor.fetchall()
            assert len(seg_rows) >= 2, f"Expected at least 2 segments, got {len(seg_rows)}"

            for idx, (seg_id,) in enumerate(seg_rows):
                art_file = tmp_path / "artifacts" / f"rendered_seg_{idx}.wav"
                generate_valid_wav(art_file, duration_s=1.2, sample_rate=48000)
                art_id = f"art_e2e_{idx}_{int(time.time())}"
                cursor.execute(
                    """INSERT INTO artifacts (id, owner_id, file_path, file_size_bytes, duration_seconds, sample_rate, format, file_hash_sha256, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (art_id, user_id, str(art_file), art_file.stat().st_size, 1.2, 48000, "wav", f"sha_seg_{idx}")
                )
                cursor.execute(
                    "UPDATE script_segments SET active_artifact_id = ?, status = 'completed', updated_at = datetime('now') WHERE id = ?",
                    (art_id, seg_id)
                )

            conn.commit()
            conn.close()

            # Step 8: Sync UI with completed segment status via Reconcile button
            page.click('button[title="Đồng bộ trạng thái xử lý nền"]')
            page.wait_for_selector("text=2 / 2", timeout=10000)

            # Step 9: Open Master Export Modal -> Verify ready to export
            page.click('button:has-text("Xuất Bản Master DSP")')
            page.wait_for_selector("text=Xuất Bản Âm Thanh Master (DSP)", timeout=5000)
            # The warning banner should NOT be present now
            assert page.locator("text=Dự án chưa sẵn sàng để xuất bản Master").count() == 0, (
                "Warning banner should disappear when all segments are completed"
            )

            # Export button must now be enabled
            export_btn = page.locator('button:has-text("Bắt Đầu Ghép Nối & Xuất Bản Master")')
            assert not export_btn.is_disabled(), "Export button should be enabled"

            # Step 10: Trigger WAV Master Export
            export_btn.click()
            page.wait_for_selector("text=Xuất bản Master thành công!", timeout=15000)

            # Verify metrics displayed
            page.wait_for_selector("text=WAV (48000Hz)", timeout=5000)
            page.wait_for_selector("text=ÂM LƯỢNG LUFS", timeout=5000)

            # Capture authentic screenshot of verified export success modal
            screenshot_path = SCREENSHOT_DIR / "phase4_06_browser_download_verified.png"
            page.screenshot(path=str(screenshot_path))
            assert screenshot_path.is_file(), f"Screenshot not found at {screenshot_path}"

            # Step 11: Real Browser Download Interception via Playwright
            download_btn = page.locator('a:has-text("Tải File Âm Thanh Master Ngay (WAV)")')
            assert download_btn.is_visible()

            # Verify href contains ?token= query parameter
            href = download_btn.get_attribute("href")
            assert href is not None
            assert "/download?token=" in href, f"Download URL missing token query parameter: {href}"

            with page.expect_download(timeout=10000) as download_info:
                download_btn.click()

            download = download_info.value
            downloaded_wav_path = tmp_path / "downloaded_master_studio.wav"
            download.save_as(str(downloaded_wav_path))

            # Step 12: Verify downloaded WAV binary
            assert downloaded_wav_path.is_file(), "Downloaded file does not exist on disk"
            wav_size = downloaded_wav_path.stat().st_size
            assert wav_size > 2000, f"Downloaded WAV size too small: {wav_size} bytes"

            with wave.open(str(downloaded_wav_path), "rb") as wf:
                assert wf.getnchannels() in (1, 2)
                assert wf.getsampwidth() == 2  # 16-bit PCM
                assert wf.getframerate() == 48000
                frames = wf.getnframes()
                duration = frames / wf.getframerate()
                assert duration > 2.0, f"Expected duration > 2.0s, got {duration}s"

            # Step 13: Export as MP3 from UI to test dual format download
            page.select_option('select:has(option[value="mp3"])', value="mp3")
            page.click('button:has-text("Bắt Đầu Ghép Nối & Xuất Bản Master")')

            mp3_download_btn = page.locator('a:has-text("Tải File Âm Thanh Master Ngay (MP3)")')
            mp3_download_btn.wait_for(state="visible", timeout=15000)

            with page.expect_download(timeout=10000) as mp3_dl_info:
                mp3_download_btn.click()

            mp3_download = mp3_dl_info.value
            downloaded_mp3_path = tmp_path / "downloaded_master_studio.mp3"
            mp3_download.save_as(str(downloaded_mp3_path))
            assert downloaded_mp3_path.is_file()
            assert downloaded_mp3_path.stat().st_size > 1000

            # Step 14: Verify Export History and Re-download
            page.wait_for_selector("text=Lịch sử các bản Master trước đó", timeout=5000)
            history_dl_buttons = page.locator('a[title="Tải về"]')
            assert history_dl_buttons.count() >= 2, f"Expected >= 2 history items, got {history_dl_buttons.count()}"

            with page.expect_download(timeout=10000) as hist_dl_info:
                history_dl_buttons.nth(0).click()

            hist_dl = hist_dl_info.value
            hist_saved = tmp_path / "downloaded_from_history.bin"
            hist_dl.save_as(str(hist_saved))
            assert hist_saved.is_file() and hist_saved.stat().st_size > 1000

            # Step 15: Security & Isolation checks via HTTP client
            # Extract download URL
            parsed_href = href
            if not parsed_href.startswith("http"):
                parsed_href = f"{base_url}{parsed_href}"

            # 15a. Valid authenticated request -> 200 OK + attachment header
            req_valid = urllib.request.Request(parsed_href)
            with urllib.request.urlopen(req_valid) as resp:
                assert resp.status == 200
                cd_header = resp.headers.get("Content-Disposition", "")
                assert "attachment;" in cd_header
                assert ".wav" in cd_header

            # 15b. Unauthenticated request (strip token query param) -> 401 Unauthorized
            unauth_url = parsed_href.split("?")[0]
            with pytest.raises(urllib.error.HTTPError) as exc_401:
                urllib.request.urlopen(unauth_url)
            assert exc_401.value.code == 401, f"Expected 401, got {exc_401.value.code}"

            # 15c. Cross-user access with unauthorized token -> 403 Forbidden
            bob_token = create_access_token({"sub": "user_bob_403", "username": "author_bob", "role": "editor"})
            cross_url = f"{unauth_url}?token={bob_token}"
            with pytest.raises(urllib.error.HTTPError) as exc_403:
                urllib.request.urlopen(cross_url)
            assert exc_403.value.code == 403, f"Expected 403, got {exc_403.value.code}"

            browser.close()

        # Stop background Uvicorn server
        server.should_exit = True
        server_thread.join(timeout=3.0)

    print("Phase 4 Browser Master Export & Download E2E Test PASSED flawlessly.")
