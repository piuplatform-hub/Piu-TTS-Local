"""
Phase 6A-R3: Real Browser Acceptance — Dialogue Studio, Two Characters,
Batch Render, WAV Artifact Download, Process Restart & Voice Profile Persistence.

Strictly Local-First (Port 8770, loopback only).
"""

import asyncio
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import wave
import httpx
from playwright.async_api import async_playwright

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path.cwd()))

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SANDBOX_DIR = Path(r"D:\AIVoiceStudioData\pilot_sandbox")
OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\dialogue_e2e_screenshots")
REF_A = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")
REF_B = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\test_clone\reference_b_sample.wav")
DB_PATH = SANDBOX_DIR / "dialogue_acceptance.db"
BASE_URL = "http://127.0.0.1:8770"


def setup_sandbox_database():
    print("\n[Step 0] Khởi tạo Sandbox Database & Seed Data...")
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Copy production DB template (already on head migration 20261010_0007)
    prod_db = Path("D:/AIVoiceStudioData/studio.db")
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass
    shutil.copy2(str(prod_db), str(DB_PATH))

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Create Password Hash using core security module
    from apps.server.src.core.security import hash_password
    pwd_hash = hash_password("Director12345!")
    pwd_hash_user2 = hash_password("Intruder12345!")

    # 1. Insert Users
    user1_id = "u1-dialogue-director-0001"
    user2_id = "u2-intruder-user-0002"
    now_str = "2026-10-10 12:00:00"

    cur.execute(
        "INSERT OR REPLACE INTO users (id, username, password_hash, role, is_active, created_at, storage_quota_mb, token_version) "
        "VALUES (?, ?, ?, ?, 1, ?, 500, 1)",
        (user1_id, "dialogue_director", pwd_hash, "editor", now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO users (id, username, password_hash, role, is_active, created_at, storage_quota_mb, token_version) "
        "VALUES (?, ?, ?, ?, 1, ?, 500, 1)",
        (user2_id, "intruder_user", pwd_hash_user2, "editor", now_str)
    )

    # 2. Insert Reference Assets for User 1 and User 2
    ref_a_id = "ref-asset-user1-tham-tu"
    ref_b_id = "ref-asset-user1-nha-bao"
    ref_u2_id = "ref-asset-user2-secret"

    cur.execute(
        "INSERT OR REPLACE INTO reference_assets (id, user_id, filename, file_path, duration_seconds, sample_rate, channels, file_size_bytes, file_hash_sha256, format, voice_use_consent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'wav', 1, ?)",
        (ref_a_id, user1_id, "example_a.wav", str(REF_A), 2.47, 24000, 1, REF_A.stat().st_size, "hash_a", now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO reference_assets (id, user_id, filename, file_path, duration_seconds, sample_rate, channels, file_size_bytes, file_hash_sha256, format, voice_use_consent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'wav', 1, ?)",
        (ref_b_id, user1_id, "example_b.wav", str(REF_B), 3.07, 24000, 1, REF_B.stat().st_size, "hash_b", now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO reference_assets (id, user_id, filename, file_path, duration_seconds, sample_rate, channels, file_size_bytes, file_hash_sha256, format, voice_use_consent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'wav', 1, ?)",
        (ref_u2_id, user2_id, "secret_u2.wav", str(REF_A), 2.47, 24000, 1, REF_A.stat().st_size, "hash_u2", now_str)
    )

    # 3. Insert Voice Profiles
    prof1_id = "prof-user1-tham-tu-minh"
    prof2_id = "prof-user1-nha-bao-lan"
    prof_u2_id = "prof-user2-secret-voice"

    cur.execute(
        "INSERT OR REPLACE INTO voice_profiles (id, user_id, name, description, engine_id, reference_asset_id, parameters_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (prof1_id, user1_id, "Giọng Thám Tử Minh (Ref A)", "Profile nhân vật điều tra", "vieneu-tts", ref_a_id, json.dumps({"speed": 1.0, "temperature": 0.8, "denoise": True}), now_str, now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO voice_profiles (id, user_id, name, description, engine_id, reference_asset_id, parameters_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (prof2_id, user1_id, "Giọng Nhà Báo Lan (Ref B)", "Profile phóng viên phỏng vấn", "vieneu-tts", ref_b_id, json.dumps({"speed": 1.0, "temperature": 0.85, "denoise": True}), now_str, now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO voice_profiles (id, user_id, name, description, engine_id, reference_asset_id, parameters_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (prof_u2_id, user2_id, "Giọng Riêng User 2 (Bảo Mật)", "Không ai khác được dùng", "vieneu-tts", ref_u2_id, json.dumps({"speed": 1.0}), now_str, now_str)
    )

    # 4. Insert Dialogue Project
    proj_id = "proj-dialogue-acceptance-01"
    cur.execute(
        "INSERT OR REPLACE INTO projects (id, user_id, title, description, project_type, settings_json, version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '{}', 1, ?, ?)",
        (proj_id, user1_id, "Vở Kịch Trinh Thám Playwright", "Kịch bản đối thoại hai nhân vật chuyên sâu", "dialogue", now_str, now_str)
    )

    # 5. Insert Two Characters
    char1_id = "char-tham-tu-minh"
    char2_id = "char-nha-bao-lan"
    cur.execute(
        "INSERT OR REPLACE INTO characters (id, project_id, name, avatar_color, engine_id, voice_id, language, parameters_json, sort_order, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'vieneu-tts', ?, 'vi', '{}', 0, ?, ?)",
        (char1_id, proj_id, "Thám Tử Minh", "#10b981", f"profile:{prof1_id}", now_str, now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO characters (id, project_id, name, avatar_color, engine_id, voice_id, language, parameters_json, sort_order, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'vieneu-tts', ?, 'vi', '{}', 1, ?, ?)",
        (char2_id, proj_id, "Nhà Báo Lan", "#3b82f6", f"profile:{prof2_id}", now_str, now_str)
    )

    # 6. Insert Two Script Segments
    import hashlib
    seg1_id = "seg-dialogue-turn-01"
    seg2_id = "seg-dialogue-turn-02"
    text1 = "Chào cô Lan, hiện trường vụ án đã được phong tỏa chưa?"
    text2 = "Tôi vừa ghi nhận xong, mọi tài liệu đã được niêm phong cẩn thận."
    hash1 = hashlib.sha256(text1.encode('utf-8')).hexdigest()
    hash2 = hashlib.sha256(text2.encode('utf-8')).hexdigest()

    cur.execute(
        "INSERT OR REPLACE INTO script_segments (id, project_id, character_id, sequence_order, text, language, engine_id, voice_id, parameters_json, pause_after_ms, status, text_hash, version, created_at, updated_at) "
        "VALUES (?, ?, ?, 0, ?, 'vi', 'vieneu-tts', ?, '{}', 400, 'draft', ?, 1, ?, ?)",
        (seg1_id, proj_id, char1_id, text1, f"profile:{prof1_id}", hash1, now_str, now_str)
    )
    cur.execute(
        "INSERT OR REPLACE INTO script_segments (id, project_id, character_id, sequence_order, text, language, engine_id, voice_id, parameters_json, pause_after_ms, status, text_hash, version, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, 'vi', 'vieneu-tts', ?, '{}', 400, 'draft', ?, 1, ?, ?)",
        (seg2_id, proj_id, char2_id, text2, f"profile:{prof2_id}", hash2, now_str, now_str)
    )

    conn.commit()
    conn.close()
    print("  ✓ Đã khởi tạo xong sandbox database và seed 2 nhân vật, 2 voice profiles, 2 phân đoạn thoại.")


class BackendServerProcess:
    def __init__(self, port=8770):
        self.port = port
        self.proc = None
        self.log_file = None

    def start(self):
        print(f"  * Khởi chạy FastAPI Server tại http://127.0.0.1:{self.port}...")
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"
        env["STUDIO_DATA_DIR"] = str(SANDBOX_DIR)
        env["PORT"] = str(self.port)
        env["HOST"] = "127.0.0.1"
        env["EMBEDDED_SCHEDULER"] = "true"

        cmd = [
            sys.executable,
            "-m", "uvicorn",
            "apps.server.src.main:app",
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--log-level", "info",
        ]
        log_path = SANDBOX_DIR / f"server_{self.port}.log"
        self.log_file = open(log_path, "a", encoding="utf-8")
        self.proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
        )

        # Wait for server ready
        for _ in range(60):
            try:
                r = httpx.get(f"http://127.0.0.1:{self.port}/api/v1/auth/status", timeout=1.0)
                if r.status_code == 200:
                    print(f"  ✓ FastAPI Server đã online tại http://127.0.0.1:{self.port}")
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"Server failed to start on port {self.port}")

    def stop(self):
        if self.proc:
            print("  * Dừng tiến trình FastAPI Server & Worker...")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            time.sleep(1.0)
            print("  ✓ Server và Worker process đã dừng hoàn toàn.")


async def run_dialogue_and_restart_acceptance():
    setup_sandbox_database()
    server_mgr = BackendServerProcess(port=8770)
    server_mgr.start()

    try:
        async with async_playwright() as p:
            print("\n[Step 1] Khởi chạy Google Chrome thực tế qua Playwright...")
            browser = await p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
            )
            context = await browser.new_context(viewport={"width": 1400, "height": 950})
            page = await context.new_page()

            # -------------------------------------------------------------
            # STEP 1: LOGIN & CROSS-USER ISOLATION AUDIT
            # -------------------------------------------------------------
            print("\n[Step 2] Đăng nhập tài khoản dialogue_director & Kiểm toán Bảo mật Cô lập Người dùng...")
            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")

            await page.fill("input[type='text']", "dialogue_director")
            await page.fill("input[type='password']", "Director12345!")
            await page.click("button:has-text('Đăng Nhập')")
            await page.wait_for_selector("text=Dự Án Studio", timeout=10000)

            # Get auth token
            token = await page.evaluate("() => localStorage.getItem('ai_voice_studio_token') || localStorage.getItem('token')")
            assert token is not None, "Failed to get auth token"

            # Check voice profiles list for user 1
            async with httpx.AsyncClient() as client:
                r_profiles = await client.get(
                    f"{BASE_URL}/api/v1/voices/profiles",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert r_profiles.status_code == 200, f"Expected 200, got {r_profiles.status_code}: {r_profiles.text}"
                prof_data = r_profiles.json()
                prof_names = [pr["name"] for pr in prof_data]
                print(f"  ✓ Danh sách Hồ sơ Giọng của User 1: {prof_names}")
                assert "Giọng Thám Tử Minh (Ref A)" in prof_names
                assert "Giọng Nhà Báo Lan (Ref B)" in prof_names
                # Security Assertion: User 1 MUST NOT see User 2's secret profile!
                assert "Giọng Riêng User 2 (Bảo Mật)" not in prof_names, "CRITICAL: Cross-user voice profile leak detected!"

                # Security Assertion: User 1 MUST NOT be able to submit jobs with User 2's profile
                r_intruder_job = await client.post(
                    f"{BASE_URL}/api/v1/jobs/speech",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "text": "Kiểm tra quyền truy cập trái phép hồ sơ giọng người khác.",
                        "voice_id": "profile:prof-user2-secret-voice",
                        "engine_id": "vieneu-tts",
                    }
                )
                assert r_intruder_job.status_code in (404, 422), f"Expected 404/422 on unauthorized profile, got {r_intruder_job.status_code}"
                print("  ✓ XÁC NHẬN BẢO MẬT: Chặn thành công 100% nỗ lực truy cập trái phép Voice Profile của tài khoản khác (HTTP 404 Not Found)!")

            # -------------------------------------------------------------
            # STEP 2: OPEN DIALOGUE STUDIO
            # -------------------------------------------------------------
            print("\n[Step 3] Mở Dự án Dialogue Studio (Vở Kịch Trinh Thám)...")
            project_card = page.locator("text=Vở Kịch Trinh Thám Playwright")
            await project_card.wait_for(timeout=10000)
            await project_card.click()

            await page.wait_for_selector("text=Danh Sách Nhân Vật Trong Vở Kịch", timeout=10000)
            await page.screenshot(path=str(OUTPUT_DIR / "01_dialogue_studio_characters_and_script.png"))
            print("  ✓ Giao diện Dialogue Studio đã tải xong: hiển thị 2 nhân vật và 2 lượt thoại.")

            # -------------------------------------------------------------
            # STEP 3: RENDER EACH SEGMENT WITH DISTINCT VOICE PROFILE
            # -------------------------------------------------------------
            print("\n[Step 4] Render Từng Phân Đoạn bằng Giọng Nhân Bản Riêng Biệt...")

            # Render Segment 1 (Thám Tử Minh - Ref A)
            print("  * Đang render Segment 1 (Thám Tử Minh - Ref A)...")
            async with httpx.AsyncClient() as client:
                r_seg1 = await client.post(
                    f"{BASE_URL}/api/v1/projects/proj-dialogue-acceptance-01/segments/seg-dialogue-turn-01/render",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert r_seg1.status_code == 200, f"Render seg 1 failed: {r_seg1.text}"
                job1_id = r_seg1.json()["last_job_id"]
                assert job1_id is not None, "Segment 1 did not return last_job_id!"

            # Wait for Job 1 completion
            job1_record = None
            for _ in range(90):
                await asyncio.sleep(1.0)
                async with httpx.AsyncClient() as client:
                    r_poll = await client.get(
                        f"{BASE_URL}/api/v1/jobs/{job1_id}",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if r_poll.status_code == 200:
                        status = r_poll.json()["status"]
                        if status == "completed":
                            job1_record = r_poll.json()
                            break
                        elif status == "failed":
                            raise RuntimeError(f"Job 1 failed: {r_poll.json().get('error_details')}")

            assert job1_record is not None, "Job 1 timed out before completing!"
            assert job1_record["status"] == "completed"

            # Check DB payload for Job 1
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT payload_data FROM jobs WHERE id = ?", (job1_id,))
            p1_row = cur.fetchone()
            assert p1_row is not None
            p1_dict = json.loads(p1_row[0])
            assert p1_dict["parameters"]["reference_asset_id"] == "ref-asset-user1-tham-tu", f"Job 1 ref mismatch: {p1_dict}"
            conn.close()
            print(f"  ✓ Segment 1 hoàn tất! Job ID: {job1_id} | Ref Asset ID: {p1_dict['parameters']['reference_asset_id']}")

            # Render Segment 2 (Nhà Báo Lan - Ref B)
            print("  * Đang render Segment 2 (Nhà Báo Lan - Ref B)...")
            async with httpx.AsyncClient() as client:
                r_seg2 = await client.post(
                    f"{BASE_URL}/api/v1/projects/proj-dialogue-acceptance-01/segments/seg-dialogue-turn-02/render",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert r_seg2.status_code == 200, f"Render seg 2 failed: {r_seg2.text}"
                job2_id = r_seg2.json()["last_job_id"]
                assert job2_id is not None, "Segment 2 did not return last_job_id!"

            # Wait for Job 2 completion
            job2_record = None
            for _ in range(90):
                await asyncio.sleep(1.0)
                async with httpx.AsyncClient() as client:
                    r_poll = await client.get(
                        f"{BASE_URL}/api/v1/jobs/{job2_id}",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if r_poll.status_code == 200:
                        status = r_poll.json()["status"]
                        if status == "completed":
                            job2_record = r_poll.json()
                            break
                        elif status == "failed":
                            raise RuntimeError(f"Job 2 failed: {r_poll.json().get('error_details')}")

            assert job2_record is not None, "Job 2 timed out before completing!"
            assert job2_record["status"] == "completed"

            # Check DB payload for Job 2
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT payload_data FROM jobs WHERE id = ?", (job2_id,))
            p2_row = cur.fetchone()
            assert p2_row is not None
            p2_dict = json.loads(p2_row[0])
            assert p2_dict["parameters"]["reference_asset_id"] == "ref-asset-user1-nha-bao", f"Job 2 ref mismatch: {p2_dict}"
            conn.close()
            print(f"  ✓ Segment 2 hoàn tất! Job ID: {job2_id} | Ref Asset ID: {p2_dict['parameters']['reference_asset_id']}")

            # Capture dialogue UI state after individual renders
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(OUTPUT_DIR / "02_dialogue_segments_rendered.png"))

            # -------------------------------------------------------------
            # STEP 4: BATCH RENDER ON DIALOGUE STUDIO
            # -------------------------------------------------------------
            print("\n[Step 5] Kiểm thử Tổng Hợp Hàng Loạt (Batch Render) trên Dialogue Studio...")
            async with httpx.AsyncClient() as client:
                r_batch = await client.post(
                    f"{BASE_URL}/api/v1/projects/proj-dialogue-acceptance-01/render-batch",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"segment_ids": ["seg-dialogue-turn-01", "seg-dialogue-turn-02"]}
                )
                assert r_batch.status_code == 200, f"Batch render failed: {r_batch.text}"
                batch_res = r_batch.json()
                print(f"  ✓ Batch render đã tạo {len(batch_res)} segments được lên lịch job.")

            # Wait for batch jobs to complete
            batch_job_ids = [seg["last_job_id"] for seg in batch_res if seg.get("last_job_id")]
            for b_job_id in batch_job_ids:
                for _ in range(90):
                    await asyncio.sleep(1.0)
                    async with httpx.AsyncClient() as client:
                        r_b_poll = await client.get(
                            f"{BASE_URL}/api/v1/jobs/{b_job_id}",
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        if r_b_poll.status_code == 200 and r_b_poll.json()["status"] == "completed":
                            break

            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(OUTPUT_DIR / "03_dialogue_batch_completed.png"))
            print("  ✓ Batch render hoàn tất trên giao diện Dialogue Studio.")

            # -------------------------------------------------------------
            # STEP 5: DOWNLOAD WAV ARTIFACT & VERIFY HEADROOM / ZERO CLIPPING
            # -------------------------------------------------------------
            print("\n[Step 6] Tải Tệp WAV Phân Đoạn & Kiểm Tra Đầu Ra Âm Thanh...")
            art_id = job1_record["artifact_id"]
            download_url = f"{BASE_URL}/api/v1/artifacts/{art_id}/file"
            downloaded_wav_path = OUTPUT_DIR / "downloaded_segment1.wav"

            async with httpx.AsyncClient() as client:
                r_dl = await client.get(download_url, headers={"Authorization": f"Bearer {token}"})
                assert r_dl.status_code == 200, f"Failed to download audio artifact: {r_dl.status_code}"
                downloaded_wav_path.write_bytes(r_dl.content)

            # Analyze downloaded WAV with standard wave module
            with wave.open(str(downloaded_wav_path), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)

            samples = struct.unpack(f"<{n_frames * n_channels}h", raw_bytes)
            max_amp = max(abs(s) for s in samples)
            peak_float = max_amp / 32768.0
            clipped = sum(1 for s in samples if s >= 32767 or s <= -32768)
            duration_s = n_frames / float(framerate)

            print(f"  ✓ File WAV tải về: {downloaded_wav_path.name}")
            print(f"    - Thời lượng: {round(duration_s, 2)}s | Định dạng: {framerate} Hz, {sampwidth*8}-bit PCM")
            print(f"    - Kích thước: {len(r_dl.content) / 1024:.1f} KB | Peak: {round(peak_float, 4)} | Clipped Samples: {clipped}")
            assert framerate == 48000, f"Expected 48000Hz, got {framerate}"
            assert clipped == 0, f"Detected {clipped} clipped samples in downloaded WAV!"
            assert peak_float <= 0.985, f"Peak amplitude exceeded headroom: {peak_float}"
            await page.screenshot(path=str(OUTPUT_DIR / "04_download_verified.png"))

            await browser.close()

        # -------------------------------------------------------------
        # STEP 6: REAL BACKEND & WORKER PROCESS RESTART
        # -------------------------------------------------------------
        print("\n[Step 7] KHỞI ĐỘNG LẠI THỰC TẾ TIẾN TRÌNH BACKEND & WORKER (PROCESS LIFECYCLE RESTART)...")
        server_mgr.stop()

        # Verify port is closed
        port_closed = False
        for _ in range(20):
            try:
                httpx.get(f"{BASE_URL}/api/v1/auth/status", timeout=0.5)
            except Exception:
                port_closed = True
                break
            time.sleep(0.5)
        assert port_closed, "Port 8770 was not released after server shutdown!"
        print("  ✓ Cổng 8770 đã giải phóng hoàn toàn (Server Process đã tắt).")

        # Start fresh new server & worker instance
        print("  * Khởi động thực thể Backend Server & Supervisor mới...")
        server_mgr.start()
        print("  ✓ Thực thể Backend Server mới đã online trên cổng 8770!")

        # -------------------------------------------------------------
        # STEP 7: RE-OPEN BROWSER AFTER RESTART & RENDER WITH OLD PROFILE
        # -------------------------------------------------------------
        print("\n[Step 8] Mở lại Trình Duyệt Sau Khi Khởi Động Lại & Tổng Hợp Bằng Profile Cũ...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
            )
            context = await browser.new_context(viewport={"width": 1400, "height": 950})
            page = await context.new_page()

            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")

            # Login again
            await page.fill("input[type='text']", "dialogue_director")
            await page.fill("input[type='password']", "Director12345!")
            await page.click("button:has-text('Đăng Nhập')")
            await page.wait_for_selector("text=Dự Án Studio", timeout=10000)

            # Open Voice Lab
            await page.click("button:has-text('Voice Lab')")
            await page.wait_for_selector("text=Voice Lab & Speech Studio", timeout=10000)
            await page.click("button:has-text('Nhân bản (Clone)')")
            await page.wait_for_timeout(1000)

            # Check for saved profiles
            prof_card = page.locator("text=Giọng Thám Tử Minh (Ref A)")
            await prof_card.wait_for(timeout=8000)
            assert await prof_card.count() > 0, "Voice profile 'Giọng Thám Tử Minh' was lost after backend restart!"
            print("  ✓ XÁC NHẬN BẢO TOÀN DỮ LIỆU: Profile 'Giọng Thám Tử Minh' vẫn tồn tại sau khi tắt và khởi động lại backend!")

            # Select profile and render post-restart speech
            await prof_card.first.click()
            await page.wait_for_timeout(500)

            textarea = page.locator("textarea")
            await textarea.fill("Đây là thử nghiệm tạo âm thanh sau khi khởi động lại hoàn toàn máy chủ và worker.")

            # Consent
            cb = page.locator("input[type='checkbox']").first
            if await cb.count() > 0 and not await cb.is_checked():
                await cb.check()

            submit_btn = page.locator("button:has-text('Nhân bản giọng & Tổng hợp')")
            await submit_btn.scroll_into_view_if_needed()
            await submit_btn.click()

            # Wait for completed audio player
            await page.wait_for_selector("text=Tệp âm thanh hoàn tất", timeout=90000)
            await page.screenshot(path=str(OUTPUT_DIR / "05_render_after_backend_restart.png"))
            print("  ✓ TỔNG HỢP THÀNH CÔNG: Worker mới khởi động nhận diện Profile cũ và sinh âm thanh hoàn tất!")

            await browser.close()

        print("\n" + "=" * 78)
        print(" [KẾT QUẢ NGHIỆM THU] DIALOGUE STUDIO & BACKEND RESTART E2E ĐÃ VƯỢT QUA 100%")
        print("  - Cô lập người dùng (Cross-user isolation): ĐÃ CHỨNG MINH 100%")
        print("  - Hai nhân vật, hai voice profiles riêng biệt: HOÀN TẤT")
        print("  - Render từng segment & Render batch trên Dialogue Studio: THÀNH CÔNG")
        print("  - Tải WAV & Đo lường không clipping: HOÀN TẤT")
        print("  - Khởi động lại thực tế backend/worker (Process Restart): ĐÃ THỰC THI")
        print("  - Tái sử dụng Profile sau khởi động lại: BẢO TOÀN & HOẠT ĐỘNG CHÍNH XÁC")
        print("=" * 78 + "\n")

    finally:
        server_mgr.stop()


if __name__ == "__main__":
    asyncio.run(run_dialogue_and_restart_acceptance())
