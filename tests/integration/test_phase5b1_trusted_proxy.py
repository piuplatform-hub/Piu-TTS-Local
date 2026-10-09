"""
Integration Test Suite for Milestone 5B-1:
Trusted Reverse Proxy Client Identity, Rate Limiting Isolation & Gateway Hardening
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.requests import Request

from apps.server.src.config import settings
from apps.server.src import database
from apps.server.src.core.network import normalize_ip, extract_client_ip
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.models.user import User
from apps.server.src.services.login_protection_service import LoginProtectionService
from apps.server.src.services.auth_service import AuthService
from apps.server.src.runner import RunnerProcessLock


def make_mock_request(
    client_ip: str,
    headers: dict | None = None,
    client_port: int = 50000,
) -> Request:
    """Helper to build a Starlette Request with specific client socket and headers."""
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": raw_headers,
        "client": (client_ip, client_port),
        "server": ("127.0.0.1", 8765),
    }
    return Request(scope)


class TestClientIpExtraction:
    """Verifies normalize_ip and extract_client_ip under all RFC 7239 / OWASP test cases."""

    def test_normalize_ip_valid_cases(self):
        assert normalize_ip("192.168.1.1") == "192.168.1.1"
        assert normalize_ip(" 10.0.0.5 ") == "10.0.0.5"
        assert normalize_ip("192.168.1.50:54321") == "192.168.1.50"
        assert normalize_ip("::1") == "::1"
        assert normalize_ip("2001:db8::1") == "2001:db8::1"
        assert normalize_ip("[2001:db8::1]:8443") == "2001:db8::1"
        assert normalize_ip("[fe80::1ff:fe23:4567:890a]") == "fe80::1ff:fe23:4567:890a"

    def test_normalize_ip_invalid_and_injections(self):
        assert normalize_ip("") is None
        assert normalize_ip("   ") is None
        assert normalize_ip("invalid_host") is None
        assert normalize_ip("256.256.256.256") == None
        assert normalize_ip("192.168.1.1.1") is None
        assert normalize_ip("; DROP TABLE users; --") is None
        assert normalize_ip("<script>alert(1)</script>") is None
        assert normalize_ip("1.2.3.4:abc") is None
        assert normalize_ip("1.2.3.4:99999") is None  # port portion does not parse as single colon int/IPv4

    def test_untrusted_peer_ignores_x_forwarded_for(self):
        # Peer 198.51.100.1 is not in settings.TRUSTED_PROXIES ("127.0.0.1", "::1")
        req = make_mock_request(
            client_ip="198.51.100.1",
            headers={"X-Forwarded-For": "203.0.113.50", "X-Real-IP": "203.0.113.50"},
        )
        resolved = extract_client_ip(req)
        assert resolved == "198.51.100.1", "Forwarded headers must be ignored for untrusted socket peers"

    def test_trusted_proxy_extracts_x_forwarded_for(self):
        # Peer is trusted 127.0.0.1
        req = make_mock_request(
            client_ip="127.0.0.1",
            headers={"X-Forwarded-For": "192.168.1.75"},
        )
        resolved = extract_client_ip(req)
        assert resolved == "192.168.1.75", "Legitimate forwarded IP must be extracted behind trusted proxy"

    def test_trusted_proxy_extracts_x_real_ip_fallback(self):
        req = make_mock_request(
            client_ip="127.0.0.1",
            headers={"X-Real-IP": "192.168.1.88"},
        )
        resolved = extract_client_ip(req)
        assert resolved == "192.168.1.88"

    def test_trusted_proxy_chain_resolution(self):
        # Chain: [client 192.168.1.99, intermediate proxy 127.0.0.1]
        req = make_mock_request(
            client_ip="127.0.0.1",
            headers={"X-Forwarded-For": "192.168.1.99, 127.0.0.1"},
        )
        resolved = extract_client_ip(req)
        assert resolved == "192.168.1.99"

    def test_malformed_header_safe_fallback(self):
        req = make_mock_request(
            client_ip="127.0.0.1",
            headers={"X-Forwarded-For": "garbage_ip_string, ;injection;"},
        )
        resolved = extract_client_ip(req)
        assert resolved == "127.0.0.1", "Malformed forwarded header must safely fall back to peer IP"


@pytest.mark.asyncio
class TestGatewayRateLimitingIsolation:
    """Verifies multi-client isolation and protection behind the reverse proxy."""

    async def test_multi_client_rate_limiting_isolation_behind_proxy(self, test_env):
        """
        Client A (192.168.1.10) and Client B (192.168.1.20) both access through 127.0.0.1 proxy.
        Client A fails 5 times -> locked out.
        Client B must NOT be locked out and can log in normally.
        """
        async with database.AsyncSessionLocal() as session:
            # Create two test users
            u_a = User(id="user_a", username="editor_a", password_hash=hash_password("PassA123!"), role="editor")
            u_b = User(id="user_b", username="editor_b", password_hash=hash_password("PassB456!"), role="editor")
            session.add_all([u_a, u_b])
            await session.commit()

            ip_a = "192.168.1.10"
            ip_b = "192.168.1.20"

            # Client A fails 5 times
            for _ in range(5):
                await LoginProtectionService.record_attempt(session, ip_a, "editor_a", success=False)

            # Check: Client A is locked out
            is_lim_a, retry_a = await LoginProtectionService.check_rate_limit(session, ip_a, "editor_a")
            assert is_lim_a, "Client A should be locked out after 5 failures"
            assert retry_a > 0

            # Check: Client B is NOT locked out
            is_lim_b, retry_b = await LoginProtectionService.check_rate_limit(session, ip_b, "editor_b")
            assert not is_lim_b, "Client B must NOT be locked out due to Client A's failures"
            assert retry_b == 0

            # Client B successfully authenticates
            auth_b = await AuthService.authenticate_user(session, "editor_b", "PassB456!", ip_address=ip_b)
            assert auth_b.id == "user_b"

    async def test_distributed_attack_triggers_account_level_lockout(self, test_env):
        """
        Attacker rotates 10 distinct forwarded IPs targeting account 'admin_target'.
        Verifies Tier 2 account-level lockout triggers at 10 failed attempts across all IPs.
        """
        async with database.AsyncSessionLocal() as session:
            target_user = "admin_target"
            u = User(id="user_target", username=target_user, password_hash=hash_password("SuperSecret!"), role="admin")
            session.add(u)
            await session.commit()

            # Record 10 failed attempts from 10 distinct IPs behind the proxy
            for i in range(10):
                fake_ip = f"192.168.10.{i+1}"
                await LoginProtectionService.record_attempt(session, fake_ip, target_user, success=False)

            # Check: Next attempt from a brand new IP (192.168.10.99) is locked out under account tier
            is_lim, retry = await LoginProtectionService.check_rate_limit(session, "192.168.10.99", target_user)
            assert is_lim, "Account must be locked out after 10 failed attempts across distributed IPs"
            assert retry > 0

    async def test_source_ip_spraying_lockout(self, test_env):
        """
        Single forwarded client IP (192.168.5.50) sprays passwords across 20 distinct usernames.
        Verifies Tier 3 source-IP lockout triggers after 20 failed attempts.
        """
        async with database.AsyncSessionLocal() as session:
            attacker_ip = "192.168.5.50"
            for i in range(20):
                await LoginProtectionService.record_attempt(session, attacker_ip, f"victim_{i}", success=False)

            # Check: Any further attempt from this IP, even for an un-attacked account, is locked out
            is_lim, retry = await LoginProtectionService.check_rate_limit(session, attacker_ip, "innocent_user")
            assert is_lim, "Source IP must be locked out after 20 failed attempts across different accounts"
            assert retry > 0


class TestRunnerUniquenessLock:
    """Verifies that the standalone runner single-instance lock prevents competing runners."""

    def test_runner_lock_acquire_and_reject_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = Path(td) / ".runner.lock"

            lock1 = RunnerProcessLock(lock_path)
            assert lock1.acquire() is True, "First runner lock acquisition must succeed"

            # Second runner instance attempting to acquire the same lock
            lock2 = RunnerProcessLock(lock_path)
            assert lock2.acquire() is False, "Second runner instance must be rejected while lock is held"

            # Release first lock
            lock1.release()

            # Now second runner instance can acquire
            lock3 = RunnerProcessLock(lock_path)
            assert lock3.acquire() is True, "Lock acquisition must succeed after release"
            lock3.release()


@pytest.mark.asyncio
class TestSecurityBaselinePreservation:
    """Ensures Phase 4 & 5A security baseline (Bearer JWT only, query tokens rejected) remains intact."""

    async def test_audio_endpoints_reject_query_tokens(self, client: AsyncClient, test_env):
        """Verify that passing query token (?token=...) is strictly rejected with HTTP 400 or 401."""
        # 1. Unauthenticated request with only query token fails authentication (401)
        resp_unauth = await client.get("/api/v1/projects/proj-123/exports/exp-456/download?token=fake-token")
        assert resp_unauth.status_code == 401

        # 2. Authenticated user providing query token is rejected with HTTP 400 QUERY_AUTH_PROHIBITED
        async with database.AsyncSessionLocal() as session:
            test_user = User(id="user_audio_test", username="audio_tester", password_hash=hash_password("Pass123!"), role="admin")
            session.add(test_user)
            await session.commit()

        token = create_access_token({"sub": "user_audio_test", "username": "audio_tester", "role": "admin"})
        headers = {"Authorization": f"Bearer {token}"}

        # Test projects export download with query token
        resp_export = await client.get(
            "/api/v1/projects/proj-123/exports/exp-456/download?token=fake-token",
            headers=headers,
        )
        assert resp_export.status_code == 400
        data_export = resp_export.json()
        assert data_export.get("code") == "QUERY_AUTH_PROHIBITED"

        # Test artifacts audio stream with query token
        resp_art = await client.get(
            "/api/v1/artifacts/art-123/file?token=fake-token",
            headers=headers,
        )
        assert resp_art.status_code == 400
        data_art = resp_art.json()
        assert data_art.get("code") == "QUERY_AUTH_PROHIBITED"
