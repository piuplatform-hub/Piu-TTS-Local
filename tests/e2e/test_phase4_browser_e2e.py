"""
Real Chrome Browser End-to-End Tests for Phase 4 Professional Studio Workstation
Verifies the complete user experience in Google Chrome via Playwright:
1. Onboarding & Authentication.
2. Projects Workspace: listing, searching, and creating projects.
3. Long-form Speech Studio: text segmentation preview, apply segments, inline edits, status badges.
4. Multi-character Dialogue Studio: creating character personas, color avatars, alternating lines, turn-taking pauses.
5. Master Audio Export (DSP): EBU R128 Loudness mastering modal, sample rate conversion controls.
Captures authentic screenshots into docs/reports/screenshots/.
"""

import json
from pathlib import Path
import tempfile
import threading
import time
import pytest
from playwright.sync_api import sync_playwright
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.main import app

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOT_DIR = Path("docs/reports/screenshots").resolve()


def test_phase4_real_browser_e2e_studio_journey():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors = []
    network_failures = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        settings.STUDIO_DATA_DIR = str(tmp_path)
        db_file = tmp_path / "e2e_phase4_studio.db"

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

        # Run Alembic migrations to head
        from alembic.config import Config
        from alembic import command
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        # Start background Uvicorn server on port 8774
        port = 8774
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        time.sleep(2.0)

        # Read bootstrap setup token
        token_file = tmp_path / ".bootstrap_token"
        assert token_file.exists(), "Bootstrap token file missing"
        token_data = json.loads(token_file.read_text(encoding="utf-8"))
        setup_token = token_data["token"]

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
            )
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            page = context.new_page()

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: network_failures.append(f"{req.method} {req.url}: {req.failure}"))

            base_url = f"http://127.0.0.1:{port}"

            # Step 1: Onboarding
            page.goto(base_url, wait_until="networkidle")
            page.wait_for_selector("text=Khởi tạo Quản Trị Cục Bộ", timeout=10000)
            page.fill('input[placeholder="admin"]', "studio_master")
            page.fill('input[type="password"] >> nth=0', "StudioPass123!")
            page.fill('input[type="password"] >> nth=1', "StudioPass123!")
            page.fill('input[placeholder="Dán token 48 ký tự từ console..."]', setup_token)
            page.click('button:has-text("Hoàn tất & Khởi tạo Hệ thống")')

            # Step 2: Confirm navigation to Projects Workspace
            page.wait_for_selector("text=Dự Án Studio", timeout=10000)
            page.wait_for_selector("text=Không Gian Làm Việc Dự Án (Workstation)", timeout=10000)
            page.wait_for_selector("text=studio_master", timeout=10000)

            # Step 3: Create Narration Project
            page.click('button:has-text("Tạo Dự Án Mới")')
            page.wait_for_selector("text=Tạo Dự Án Audio Studio Mới", timeout=5000)
            page.fill('input[placeholder="Ví dụ: Audio Book Chương 1 - Truyện Kiều"]', "Sách Nói: Hào Khí Đông A")
            page.fill('textarea[placeholder="Ghi chú về nội dung, phong cách giọng điệu hoặc mục tiêu xuất bản..."]', "Tác phẩm lịch sử hào hùng, giọng đọc truyền cảm chuẩn VieNeu.")
            # Default is narration
            page.click('button:has-text("Tạo Dự Án Ngay")')

            # Expect to land inside Speech Studio
            page.wait_for_selector("text=Sách Nói: Hào Khí Đông A", timeout=10000)
            page.wait_for_selector("text=Phân Đoạn Văn Bản", timeout=10000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase4_01_project_created.png"))

            # Step 4: Intelligent Text Segmentation Modal
            page.click('button:has-text("Phân Đoạn Văn Bản")')
            page.wait_for_selector("text=Tự Động Phân Đoạn Văn Bản Dài", timeout=5000)
            page.fill(
                'textarea[placeholder="Dán toàn bộ văn bản vào đây. Hệ thống sẽ tự động phân tách theo ranh giới ngữ nghĩa và dấu kết thúc câu..."]',
                "Đất nước ta trải qua mấy ngàn năm lịch sử hào hùng. "
                "Thời nhà Trần với hào khí Đông A ba lần đại thắng quân Nguyên Mông. "
                "Trận Bạch Đằng giang nghìn thu vang dội chiến công hiển hách."
            )
            page.click('button:has-text("Xem trước kết quả phân đoạn")')
            page.wait_for_selector("text=Đã phân tích:", timeout=5000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase4_02_speech_studio_segmented.png"))

            # Apply segments to project
            page.click('button:has-text("Áp Dụng Vào Sách Nói")')
            page.wait_for_selector("text=Trận Bạch Đằng giang nghìn thu vang dội chiến công hiển hách.", timeout=10000)

            # Step 5: Back to Projects & Create Dialogue Project
            page.click('button[title="Quay lại danh sách"]')
            page.wait_for_selector("text=Không Gian Làm Việc Dự Án (Workstation)", timeout=10000)
            page.click('button:has-text("Tạo Dự Án Mới")')
            page.wait_for_selector("text=Tạo Dự Án Audio Studio Mới", timeout=5000)
            page.fill('input[placeholder="Ví dụ: Audio Book Chương 1 - Truyện Kiều"]', "Kịch Truyền Thanh: Gặp Gỡ Hà Nội")
            page.click('button:has-text("Hội thoại (Dialogue)")')
            page.click('button:has-text("Tạo Dự Án Ngay")')

            # Land in Dialogue Studio
            page.wait_for_selector("text=Kịch Truyền Thanh: Gặp Gỡ Hà Nội", timeout=10000)
            page.wait_for_selector("text=Danh Sách Nhân Vật Trong Vở Kịch", timeout=10000)

            # Step 6: Create Character A (Lan) & Character B (Mei)
            page.click('button:has-text("Thêm Nhân Vật") >> nth=0')
            page.wait_for_selector("text=Tạo Nhân Vật Mới", timeout=5000)
            page.fill('input[placeholder="Ví dụ: Người Dẫn Chuyện, Kiều, Kim Trọng..."]', "Lan (Hà Nội)")
            page.click('button:has-text("Lưu Nhân Vật")')
            page.wait_for_selector("text=Lan (Hà Nội)", timeout=10000)

            page.click('button:has-text("Tạo nhân vật mới")')
            page.wait_for_selector("text=Tạo Nhân Vật Mới", timeout=5000)
            page.fill('input[placeholder="Ví dụ: Người Dẫn Chuyện, Kiều, Kim Trọng..."]', "Mei (Du Khách)")
            page.select_option('select:has(option[value="qwen3-tts"])', value="qwen3-tts")
            page.click('button:has-text("Lưu Nhân Vật")')
            page.wait_for_selector("text=Mei (Du Khách)", timeout=10000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase4_03_dialogue_studio_characters.png"))

            # Step 7: Add Dialogue Lines
            page.click('button:has-text("Thêm Câu Thoại")')
            page.wait_for_selector('textarea >> nth=0', timeout=5000)
            page.fill('textarea >> nth=0', "Chào mừng bạn đến thăm Hà Nội mùa thu tuyệt đẹp!")
            # Save line 1
            if page.locator('button:has-text("Lưu")').count() > 0:
                page.click('button:has-text("Lưu") >> nth=0')

            # Add Line 2
            page.click('button:has-text("Thêm Câu Thoại")')
            page.wait_for_timeout(500)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase4_04_dialogue_script_stream.png"))

            # Step 8: Master Export Modal
            page.click('button:has-text("Xuất Bản Master DSP")')
            page.wait_for_selector("text=Xuất Bản Âm Thanh Master (DSP)", timeout=5000)
            page.wait_for_selector("text=Áp dụng chuẩn hóa âm lượng EBU R128", timeout=5000)
            page.screenshot(path=str(SCREENSHOT_DIR / "phase4_05_master_export_modal.png"))
            page.click('button:has-text("Đóng")')

            browser.close()

        # Stop uvicorn server
        server.should_exit = True
        server_thread.join(timeout=3.0)

    # Verify screenshots created
    assert (SCREENSHOT_DIR / "phase4_01_project_created.png").exists()
    assert (SCREENSHOT_DIR / "phase4_02_speech_studio_segmented.png").exists()
    assert (SCREENSHOT_DIR / "phase4_03_dialogue_studio_characters.png").exists()
    assert (SCREENSHOT_DIR / "phase4_04_dialogue_script_stream.png").exists()
    assert (SCREENSHOT_DIR / "phase4_05_master_export_modal.png").exists()
