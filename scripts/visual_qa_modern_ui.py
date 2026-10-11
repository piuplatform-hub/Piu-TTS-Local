"""
Visual QA Automation for AI Voice Studio Modern Desktop-First UI — Polish R1
Captures full-viewport screenshots across target viewports:
- 1920 x 1080 (Primary Workstation)
- 1440 x 900 (Laptop Standard)
- 1366 x 768 (Compact Screen)
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
        browser = p.chromium.launch(
            executable_path=CHROME_PATH if Path(CHROME_PATH).exists() else None,
            headless=True,
        )

        # -------------------------------------------------------------
        # 1. PRIMARY VIEWPORT: 1920x1080
        # -------------------------------------------------------------
        print("\n=== Capturing 1920x1080 Screens ===")
        ctx_fhd = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = ctx_fhd.new_page()

        # Login
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(500)
        page.fill("input[type='text']", "pilot_engineer_e2e")
        page.fill("input[type='password']", "Password12345!")
        page.click("button:has-text('Đăng Nhập')")
        page.wait_for_selector("text=Dự Án Studio", timeout=10000)
        page.wait_for_timeout(600)

        # Screen 1: Projects Workstation
        shot_01 = OUTPUT_DIR / "01_projects_workstation_1920x1080.png"
        page.screenshot(path=str(shot_01))
        print(f"Captured: {shot_01.name}")

        # Navigate to Speech Studio (Preset Mode by default)
        page.locator("aside button:has-text('Speech Studio')").click()
        page.wait_for_selector("h1:has-text('Speech Studio')", timeout=10000)
        page.wait_for_timeout(800)

        # Screen 2: Speech Studio Preset Mode (No Clone dropzone)
        shot_02 = OUTPUT_DIR / "02_speech_studio_preset_1920x1080.png"
        page.screenshot(path=str(shot_02))
        print(f"Captured: {shot_02.name}")

        # Switch to Clone Mode in Speech Studio
        clone_mode_btn = page.locator("button:has-text('Nhân bản (Clone)')")
        if clone_mode_btn.count() > 0:
            clone_mode_btn.first.click()
            page.wait_for_timeout(800)

        # Screen 3: Speech Studio Clone Mode (Clone Dropzone & Profiles active)
        shot_03 = OUTPUT_DIR / "03_speech_studio_clone_1920x1080.png"
        page.screenshot(path=str(shot_03))
        print(f"Captured: {shot_03.name}")

        # Navigate to Voice Lab (Redesigned)
        page.locator("aside button:has-text('Voice Lab')").click()
        page.wait_for_selector("text=Voice Lab & Speech Studio", timeout=10000)
        page.wait_for_timeout(800)

        # Screen 4: Voice Lab Redesigned Workstation
        shot_04 = OUTPUT_DIR / "04_voice_lab_redesigned_1920x1080.png"
        page.screenshot(path=str(shot_04))
        print(f"Captured: {shot_04.name}")

        # Switch to Clone Mode in Voice Lab and Open Advanced Controls
        vl_clone_btn = page.locator("button:has-text('Nhân bản (Clone)')")
        if vl_clone_btn.count() > 0:
            vl_clone_btn.first.click()
            page.wait_for_timeout(500)

        adv_btn = page.locator("button:has-text('Tinh chỉnh giọng nâng cao')")
        if adv_btn.count() > 0:
            adv_btn.first.click()
            page.wait_for_timeout(500)

        # Screen 5: Voice Lab Controls Detail (Sliders, Presets, Denoise)
        shot_05 = OUTPUT_DIR / "05_voice_lab_controls_detail_1920x1080.png"
        page.screenshot(path=str(shot_05))
        print(f"Captured: {shot_05.name}")

        # Navigate to Library (Voice Profiles Library with Search & Sort)
        page.locator("aside button:has-text('Thư viện')").click()
        page.wait_for_selector("text=Thư Viện Hồ Sơ Giọng Nói", timeout=10000)
        page.wait_for_timeout(800)

        # Screen 6: Voice Library with Search & Sort
        shot_06 = OUTPUT_DIR / "06_voice_library_search_sort_1920x1080.png"
        page.screenshot(path=str(shot_06))
        print(f"Captured: {shot_06.name}")

        # Navigate to Settings
        page.locator("aside button:has-text('Cài đặt')").click()
        page.wait_for_selector("text=Cài Đặt Hệ Thống", timeout=10000)
        page.wait_for_timeout(800)

        # Screen 7: Settings & Engine Capabilities
        shot_07 = OUTPUT_DIR / "07_settings_engine_capabilities_1920x1080.png"
        page.screenshot(path=str(shot_07))
        print(f"Captured: {shot_07.name}")

        ctx_fhd.close()

        # -------------------------------------------------------------
        # 2. LAPTOP VIEWPORT: 1440x900
        # -------------------------------------------------------------
        print("\n=== Capturing 1440x900 Screen ===")
        ctx_laptop = browser.new_context(viewport={"width": 1440, "height": 900})
        page_lap = ctx_laptop.new_page()
        page_lap.goto(BASE_URL, wait_until="networkidle")
        page_lap.wait_for_timeout(500)
        page_lap.fill("input[type='text']", "pilot_engineer_e2e")
        page_lap.fill("input[type='password']", "Password12345!")
        page_lap.click("button:has-text('Đăng Nhập')")
        page_lap.wait_for_selector("text=Dự Án Studio", timeout=10000)

        page_lap.locator("aside button:has-text('Speech Studio')").click()
        page_lap.wait_for_selector("h1:has-text('Speech Studio')", timeout=10000)
        page_lap.wait_for_timeout(800)

        shot_08 = OUTPUT_DIR / "08_responsive_1440x900.png"
        page_lap.screenshot(path=str(shot_08))
        print(f"Captured: {shot_08.name}")
        ctx_laptop.close()

        # -------------------------------------------------------------
        # 3. COMPACT VIEWPORT: 1366x768
        # -------------------------------------------------------------
        print("\n=== Capturing 1366x768 Screen ===")
        ctx_compact = browser.new_context(viewport={"width": 1366, "height": 768})
        page_cmp = ctx_compact.new_page()
        page_cmp.goto(BASE_URL, wait_until="networkidle")
        page_cmp.wait_for_timeout(500)
        page_cmp.fill("input[type='text']", "pilot_engineer_e2e")
        page_cmp.fill("input[type='password']", "Password12345!")
        page_cmp.click("button:has-text('Đăng Nhập')")
        page_cmp.wait_for_selector("text=Dự Án Studio", timeout=10000)

        page_cmp.locator("aside button:has-text('Voice Lab')").click()
        page_cmp.wait_for_selector("text=Voice Lab & Speech Studio", timeout=10000)
        page_cmp.wait_for_timeout(800)

        shot_09 = OUTPUT_DIR / "09_responsive_1366x768.png"
        page_cmp.screenshot(path=str(shot_09))
        print(f"Captured: {shot_09.name}")
        ctx_compact.close()

        browser.close()
    print("\nVisual QA completed successfully! All screenshots saved.")

if __name__ == "__main__":
    run_visual_qa()
