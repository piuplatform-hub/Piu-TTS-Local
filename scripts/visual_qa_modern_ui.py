"""
Visual QA Automation for AI Voice Studio Modern Desktop-First UI
Tests and captures screenshots across multiple resolutions:
- 1920 x 1080
- 1440 x 900
- 1366 x 768
"""

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path(r"d:\C\Dev\du an\TTS\docs\reports\screenshots\modern_ui")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8765"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def run_visual_qa():
    with sync_playwright() as p:
        # Launch Chrome
        browser = p.chromium.launch(
            executable_path=CHROME_PATH if Path(CHROME_PATH).exists() else None,
            headless=True,
        )

        resolutions = [
            (1920, 1080, "1920x1080"),
            (1440, 900, "1440x900"),
            (1366, 768, "1366x768"),
        ]

        for width, height, res_name in resolutions:
            print(f"\n--- Testing Resolution: {res_name} ({width}x{height}) ---")
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            # 1. Login
            page.goto(BASE_URL, wait_until="networkidle")
            page.wait_for_timeout(500)

            # Fill login credentials
            page.fill("input[type='text']", "pilot_engineer_e2e")
            page.fill("input[type='password']", "Password12345!")
            page.click("button:has-text('Đăng Nhập')")

            # Wait for dashboard
            page.wait_for_selector("text=Dự Án Studio", timeout=10000)
            page.wait_for_timeout(800)

            if res_name == "1920x1080":
                # Capture Projects Dashboard
                shot_path = OUTPUT_DIR / f"01_dashboard_projects_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 2. Navigate to Speech Studio
                page.click("button:has-text('Speech Studio')")
                page.wait_for_selector("h1:has-text('Speech Studio')", timeout=10000)
                page.wait_for_timeout(800)

                # Capture Main Speech Studio
                shot_path = OUTPUT_DIR / f"02_speech_studio_main_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 3. Switch to Voice Cloning mode
                page.locator("button:has-text('Bật chế độ Clone')").click()
                page.wait_for_selector("input[type='file']", state="attached", timeout=5000)
                page.wait_for_timeout(500)
                shot_path = OUTPUT_DIR / f"03_speech_studio_cloning_mode_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 4. Open Advanced Controls accordion
                adv_btn = page.query_selector("button:has-text('Tham số suy luận nâng cao')")
                if adv_btn:
                    adv_btn.click()
                    page.wait_for_timeout(500)
                shot_path = OUTPUT_DIR / f"04_speech_studio_advanced_controls_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 5. Collapse sidebar
                collapse_btn = page.query_selector("button[title*='Thu gọn']")
                if collapse_btn:
                    collapse_btn.click()
                    page.wait_for_timeout(500)
                    shot_path = OUTPUT_DIR / f"05_speech_studio_collapsed_sidebar_{res_name}.png"
                    page.screenshot(path=str(shot_path), full_page=False)
                    print(f"Captured: {shot_path.name}")

                    # Expand again
                    expand_btn = page.query_selector("button[title*='Mở rộng']")
                    if expand_btn:
                        expand_btn.click()
                        page.wait_for_timeout(500)

                # 6. Navigate to Voice Lab
                page.locator("aside button:has-text('Voice Lab')").click()
                page.wait_for_timeout(1000)
                shot_path = OUTPUT_DIR / f"06_voice_lab_view_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 7. Navigate to Library
                page.locator("aside button:has-text('Thư viện')").click()
                page.wait_for_timeout(1000)
                shot_path = OUTPUT_DIR / f"07_library_view_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

                # 8. Navigate to Settings
                page.locator("aside button:has-text('Cài đặt')").click()
                page.wait_for_timeout(1000)
                shot_path = OUTPUT_DIR / f"08_settings_view_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

            else:
                # For 1440x900 and 1366x768, navigate to Speech Studio and capture
                page.locator("aside button:has-text('Speech Studio')").click()
                page.wait_for_selector("h1:has-text('Speech Studio')", timeout=10000)
                page.wait_for_timeout(800)

                shot_path = OUTPUT_DIR / f"09_speech_studio_{res_name}.png"
                page.screenshot(path=str(shot_path), full_page=False)
                print(f"Captured: {shot_path.name}")

            context.close()

        browser.close()
    print("\nVisual QA completed successfully!")

if __name__ == "__main__":
    run_visual_qa()
