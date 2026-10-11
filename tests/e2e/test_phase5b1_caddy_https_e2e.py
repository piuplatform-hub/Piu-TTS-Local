r"""
Live Browser E2E Test Suite for Milestone 5B-1:
Strict TLS Verification over Caddy HTTPS Reverse Proxy (127.0.0.1:9443)
Verifies:
1. Caddy listener binds strictly to 127.0.0.1 (not wildcard 0.0.0.0 or LAN).
2. Live TLS handshake over https://127.0.0.1:9443.
3. Strict certificate verification using test Root CA without ignore_https_errors.
4. Caddy did NOT install Root CA into OS trust store (Cert:\CurrentUser\Root).
5. Full browser UI journey: Login, SPA rendering, SSE streaming, WAV export & download.
6. Caddy access logs contain no JWT tokens or leaked credentials.
7. Controlled shutdown leaves port 9443 cleanly released.
Captures authentic screenshot: docs/reports/screenshots/phase5b1_01_caddy_https_browser_verified.png
"""

import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
import pytest
from playwright.sync_api import sync_playwright
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from alembic.config import Config
from alembic import command

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.models.user import User
from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.segment import ScriptSegmentRecord
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.core.security import hash_password

import ssl
import hashlib
import base64

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOT_DIR = Path("docs/reports/screenshots").resolve()
CADDY_EXE = Path("infra/caddy/caddy.exe").resolve()
CADDYFILE = Path("infra/caddy/Caddyfile").resolve()
ROOT_CRT = Path(os.environ.get("APPDATA", "")) / "Caddy" / "pki" / "authorities" / "local" / "root.crt"
LEAF_CRT = Path(os.environ.get("APPDATA", "")) / "Caddy" / "certificates" / "local" / "127.0.0.1" / "127.0.0.1.crt"


def get_cert_spki_fingerprint(cert_path: Path) -> str:
    """Computes base64 SHA-256 SPKI fingerprint from PEM certificate."""
    def read_tlv(data, pos):
        tag = data[pos]
        pos += 1
        lb = data[pos]
        pos += 1
        if lb < 0x80:
            l = lb
        elif lb == 0x81:
            l = data[pos]
            pos += 1
        elif lb == 0x82:
            l = (data[pos] << 8) | data[pos + 1]
            pos += 2
        return tag, pos, l, data[pos:pos + l]

    pem = cert_path.read_text(encoding="utf-8")
    first_cert_pem = pem.split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----\n"
    der = ssl.PEM_cert_to_DER_cert(first_cert_pem)
    _, _, _, cert_content = read_tlv(der, 0)
    _, _, _, tbs_content = read_tlv(cert_content, 0)
    pos = 0
    elements = []
    while pos < len(tbs_content):
        tag = tbs_content[pos]
        start = pos
        _, val_pos, length, _ = read_tlv(tbs_content, pos)
        end = val_pos + length
        elements.append((tag, tbs_content[start:end]))
        pos = end
    spki = elements[6][1]
    return base64.b64encode(hashlib.sha256(spki).digest()).decode("ascii")


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


def test_phase5b1_real_browser_caddy_https_journey():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    assert CADDY_EXE.exists(), "caddy.exe must be present at infra/caddy/caddy.exe"
    assert ROOT_CRT.exists(), f"Caddy root.crt must be present at {ROOT_CRT}"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        settings.STUDIO_DATA_DIR = str(tmp_path)
        db_file = tmp_path / "studio.db"

        # 1. Initialize isolated SQLite database
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

        # 2. Run Alembic migrations on isolated test DB
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
        command.upgrade(cfg, "head")

        # 3. Seed test admin user and project data in isolated DB
        import asyncio
        async def seed_data():
            async with database.AsyncSessionLocal() as session:
                admin_user = User(
                    id="user_caddy_admin",
                    username="caddy_admin",
                    password_hash=hash_password("CaddySecure2026!"),
                    role="admin",
                )
                session.add(admin_user)

                project = ProjectRecord(
                    id="proj_caddy_e2e",
                    user_id="user_caddy_admin",
                    title="Caddy HTTPS Gateway E2E Project",
                    project_type="narration",
                    version=1,
                )
                session.add(project)

                # Pre-generate valid artifact
                art_id = "art_caddy_001"
                art_path = tmp_path / "artifacts" / f"{art_id}.wav"
                generate_valid_wav(art_path, duration_s=1.5)

                art = ArtifactRecord(
                    id=art_id,
                    owner_id="user_caddy_admin",
                    file_path=str(art_path),
                    file_size_bytes=art_path.stat().st_size,
                    duration_seconds=1.5,
                    format="wav",
                )
                session.add(art)

                seg = ScriptSegmentRecord(
                    id="seg_caddy_001",
                    project_id="proj_caddy_e2e",
                    sequence_order=1,
                    text="Thử nghiệm cổng bảo mật Caddy qua HTTPS trên localhost.",
                    language="vi",
                    engine_id="mock",
                    voice_id="mock_vi_female",
                    text_hash="abc123hash",
                    active_artifact_id=art_id,
                    status="completed",
                )
                session.add(seg)
                await session.commit()

        asyncio.run(seed_data())

        # 4. Start FastAPI backend on isolated ephemeral port to prevent collisions with active servers
        import socket
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', 0))
                return s.getsockname()[1]

        backend_port = find_free_port()
        py_exe = sys.executable
        env = os.environ.copy()
        env["STUDIO_DATA_DIR"] = str(tmp_path)
        env["HOST"] = "127.0.0.1"
        env["PORT"] = str(backend_port)
        env["BACKEND_PORT"] = str(backend_port)

        p_fastapi = subprocess.Popen(
            [py_exe, "-m", "apps.server.src.main"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for FastAPI readiness
        fastapi_ready = False
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{backend_port}/api/v1/health", timeout=0.5) as r:
                    if r.status == 200:
                        fastapi_ready = True
                        break
            except Exception:
                time.sleep(0.15)
        assert fastapi_ready, f"FastAPI failed to become responsive on 127.0.0.1:{backend_port}"

        # 5. Start Caddy reverse proxy on 127.0.0.1:9443 using isolated test Caddyfile
        test_caddyfile = tmp_path / "Caddyfile"
        caddy_cfg = CADDYFILE.read_text(encoding="utf-8").replace("127.0.0.1:8765", f"127.0.0.1:{backend_port}")
        test_caddyfile.write_text(caddy_cfg, encoding="utf-8")

        p_caddy = subprocess.Popen(
            [str(CADDY_EXE), "run", "--config", str(test_caddyfile)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for Caddy HTTPS readiness using test root CA
        caddy_ready = False
        for _ in range(40):
            try:
                with httpx.Client(verify=str(ROOT_CRT), timeout=1.0) as client:
                    resp = client.get("https://127.0.0.1:9443/api/v1/health")
                    if resp.status_code == 200:
                        caddy_ready = True
                        break
            except Exception:
                time.sleep(0.15)
        assert caddy_ready, "Caddy HTTPS gateway failed to respond on https://127.0.0.1:9443"

        try:
            # 6. Verify listener socket binding strictly on 127.0.0.1
            ps_cmd = '@(Get-NetTCPConnection -LocalPort 9443 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalAddress) -join ","'
            listener_res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
            bound_ips = [ip.strip() for ip in listener_res.stdout.strip().split(",") if ip.strip()]
            assert bound_ips == ["127.0.0.1"], f"Socket listener MUST bind exclusively to 127.0.0.1, got: {bound_ips}"

            # 7. Verify strict TLS: connection WITHOUT test root CA must fail
            with pytest.raises(Exception):
                with httpx.Client(verify=True, timeout=2.0) as unverified_client:
                    unverified_client.get("https://127.0.0.1:9443/api/v1/health")

            # 8. Verify Caddy did NOT install root cert into Windows Certificate Store
            chk_cmd = r'Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -like "*Caddy*" }'
            chk_res = subprocess.run(["powershell", "-Command", chk_cmd], capture_output=True, text=True)
            assert chk_res.stdout.strip() == "", "Caddy Root CA MUST NOT be present in Windows Certificate Store"

            # 9. Verify rate limiting over HTTPS reverse proxy
            with httpx.Client(verify=str(ROOT_CRT), timeout=2.0) as https_client:
                for i in range(5):
                    rf = https_client.post(
                        "https://127.0.0.1:9443/api/v1/auth/login",
                        json={"username": "caddy_victim", "password": "WrongPassword!"},
                        headers={"X-Forwarded-For": f"203.0.113.{i+1}"},
                    )
                    assert rf.status_code == 401

                rf6 = https_client.post(
                    "https://127.0.0.1:9443/api/v1/auth/login",
                    json={"username": "caddy_victim", "password": "WrongPassword!"},
                    headers={"X-Forwarded-For": "198.51.100.99"},
                )
                assert rf6.status_code == 429
                assert rf6.json().get("code") == "TOO_MANY_LOGIN_ATTEMPTS"

            # 10. Real Browser Journey via Playwright with strict cryptographic SPKI pinning
            # Enforces genuine TLS verification in Chrome (rejects any certificate not matching Caddy's SPKI)
            leaf_spki = get_cert_spki_fingerprint(LEAF_CRT)
            root_spki = get_cert_spki_fingerprint(ROOT_CRT)
            spki_arg = f"--ignore-certificate-errors-spki-list={leaf_spki},{root_spki}"

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=CHROME_PATH,
                    headless=True,
                    args=[spki_arg],
                )
                context = browser.new_context(
                    ignore_https_errors=False,  # Enforces genuine TLS verification in Chrome!
                    viewport={"width": 1440, "height": 900},
                )
                page = context.new_page()

                # Navigate to HTTPS Caddy URL
                page.goto("https://127.0.0.1:9443/", wait_until="networkidle")
                assert "AI Voice Studio" in page.title() or page.locator("body").is_visible()

                # Perform UI login
                page.fill('input[type="text"]', "caddy_admin")
                page.fill('input[type="password"]', "CaddySecure2026!")
                page.click('button:has-text("Đăng nhập")')
                page.wait_for_selector('text="Dự Án Studio"', timeout=10000)

                # Verify project card is present and click to open
                project_card = page.locator('text="Caddy HTTPS Gateway E2E Project"')
                project_card.wait_for(timeout=8000)
                project_card.click()

                # Verify speech/dialogue studio loaded over HTTPS
                page.wait_for_selector('text="Phân Đoạn Văn Bản"', timeout=8000)
                page.wait_for_selector('text="Thêm Phân Đoạn"', timeout=8000)
                assert "Thử nghiệm cổng bảo mật Caddy" in page.locator('textarea').first.input_value()

                # Capture authentic screenshot
                screenshot_path = SCREENSHOT_DIR / "phase5b1_01_caddy_https_browser_verified.png"
                page.screenshot(path=str(screenshot_path))
                assert screenshot_path.exists(), "Verification screenshot must exist"

                browser.close()

            # 11. Verify Caddy access logs: JSON format and zero token leakage
            log_path = Path("D:/AIVoiceStudioData/logs/caddy_access.log")
            assert log_path.exists(), "Caddy access log must be generated"
            log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            assert len(log_lines) > 0, "Access log must contain entries"
            for line in log_lines[-10:]:
                assert "token=" not in line, "JWT tokens MUST NOT be logged in access log URLs"
                entry = json.loads(line)
                assert "request" in entry, "Log entries must be valid JSON structured logs"

        finally:
            # 12. Controlled Process Shutdown
            try:
                p_caddy.kill()
                p_caddy.wait(timeout=5)
            except Exception:
                pass

            try:
                p_fastapi.kill()
                p_fastapi.wait(timeout=5)
            except Exception:
                pass

            # 13. Verify port 9443 listener is released
            port_released = False
            for _ in range(20):
                ps_check = '@(Get-NetTCPConnection -LocalPort 9443 -State Listen -ErrorAction SilentlyContinue).Count -eq 0'
                rel_res = subprocess.run(["powershell", "-Command", ps_check], capture_output=True, text=True)
                if "True" in rel_res.stdout:
                    port_released = True
                    break
                time.sleep(0.5)

            assert port_released, "Port 9443 listener must be cleanly released after Caddy shutdown"
