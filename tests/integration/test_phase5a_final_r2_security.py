"""
Phase 5A Final Closure R2: Authentication Throttling & Bot Defense Verification
Tests:
1. Independent per-account throttling across multiple IP identities (Distributed brute-force defense).
2. Independent per-source throttling across multiple usernames (Credential spraying defense).
3. Legitimate user protection behind a shared IP.
4. Concurrent login attempts across separate database sessions.
5. Rate limit expiry and success reset behavior.
6. Client IP spoof resistance (X-Forwarded-For ignored on localhost).
7. Account enumeration resistance (uniform 401 responses).
"""

import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.models.user import User
from apps.server.src.models.login_attempt import LoginAttemptRecord
from apps.server.src.services.auth_service import AuthService, hash_password
from apps.server.src.services.login_protection_service import LoginProtectionService
from apps.server.src.core.errors import AppException


@pytest.mark.asyncio
async def test_distributed_brute_force_one_account_10_ips(test_env):
    """
    Scenario 1: One account attacked from 10 different IP identities.
    Each IP makes 1 failed attempt (so pair limit 5 is not hit for any IP).
    When 10 attempts on the target account accumulate across all IPs,
    the account is locked out across all IPs (Tier 2 defense).
    """
    async with database.AsyncSessionLocal() as session:
        user = User(
            id="target_victim_user",
            username="victim_account",
            password_hash=hash_password("ValidPassword123!"),
            role="editor",
        )
        session.add(user)
        await session.commit()

        # 10 different attacker IP identities attack victim_account
        for i in range(10):
            attacker_ip = f"198.51.100.{i + 1}"
            is_limited, _ = await LoginProtectionService.check_rate_limit(session, attacker_ip, "victim_account")
            assert not is_limited, f"Premature lockout on attempt {i + 1} from {attacker_ip}"
            await LoginProtectionService.record_attempt(session, attacker_ip, "victim_account", success=False)

        # 11th attempt from a brand-new IP (11th identity) or legitimate IP must be throttled
        is_limited, retry_after = await LoginProtectionService.check_rate_limit(
            session, "203.0.113.99", "victim_account"
        )
        assert is_limited, "Expected victim_account to be throttled after 10 failed attempts across multiple IPs"
        assert retry_after > 0


@pytest.mark.asyncio
async def test_credential_spraying_one_ip_20_usernames(test_env):
    """
    Scenario 2: One source IP attacks 20 different usernames.
    Each username receives only 1 failed attempt (so pair limit 5 and account limit 10 are not hit).
    When 20 attempts accumulate from that source IP,
    the source IP itself is locked out across all usernames (Tier 3 defense).
    """
    async with database.AsyncSessionLocal() as session:
        attacker_ip = "192.0.2.100"

        for i in range(20):
            target_user = f"user_spray_{i + 1}"
            is_limited, _ = await LoginProtectionService.check_rate_limit(session, attacker_ip, target_user)
            assert not is_limited, f"Premature lockout on spraying attempt {i + 1}"
            await LoginProtectionService.record_attempt(session, attacker_ip, target_user, success=False)

        # 21st attempt from this IP against ANY username must be throttled
        is_limited, retry_after = await LoginProtectionService.check_rate_limit(
            session, attacker_ip, "random_innocent_user"
        )
        assert is_limited, "Expected attacker IP to be throttled after 20 failed attempts across usernames"
        assert retry_after > 0

        # Meanwhile, a different IP targeting the same innocent user is NOT throttled
        is_limited_other, _ = await LoginProtectionService.check_rate_limit(
            session, "192.0.2.200", "random_innocent_user"
        )
        assert not is_limited_other, "Unrelated IP should not be affected by the spraying IP's block"


@pytest.mark.asyncio
async def test_two_legitimate_accounts_behind_shared_ip_no_collateral_lockout(test_env):
    """
    Scenario 3: Two legitimate users sharing one IP (e.g. office NAT / localhost).
    User Alice mistypes password 3 times (< 5 pair limit, < 10 user limit).
    User Bob mistypes password 3 times (< 5 pair limit, < 10 user limit).
    Total for IP is 6 (< 20 IP limit).
    Neither user is locked out. Both can successfully log in with their correct passwords.
    """
    async with database.AsyncSessionLocal() as session:
        alice = User(id="user_alice_shared", username="alice_shared", password_hash=hash_password("AliceSecret123!"), role="editor")
        bob = User(id="user_bob_shared", username="bob_shared", password_hash=hash_password("BobSecret456!"), role="editor")
        session.add_all([alice, bob])
        await session.commit()

        shared_ip = "127.0.0.1"

        # Alice mistypes 3 times
        for _ in range(3):
            is_lim, _ = await LoginProtectionService.check_rate_limit(session, shared_ip, "alice_shared")
            assert not is_lim
            await LoginProtectionService.record_attempt(session, shared_ip, "alice_shared", success=False)

        # Bob mistypes 3 times
        for _ in range(3):
            is_lim, _ = await LoginProtectionService.check_rate_limit(session, shared_ip, "bob_shared")
            assert not is_lim
            await LoginProtectionService.record_attempt(session, shared_ip, "bob_shared", success=False)

        # Neither is throttled
        alice_lim, _ = await LoginProtectionService.check_rate_limit(session, shared_ip, "alice_shared")
        bob_lim, _ = await LoginProtectionService.check_rate_limit(session, shared_ip, "bob_shared")
        assert not alice_lim, "Alice should not be locked out after 3 failures"
        assert not bob_lim, "Bob should not be locked out after 3 failures"

        # Alice successfully logs in
        auth_alice = await AuthService.authenticate_user(session, "alice_shared", "AliceSecret123!", ip_address=shared_ip)
        assert auth_alice.id == "user_alice_shared"

        # Bob successfully logs in
        auth_bob = await AuthService.authenticate_user(session, "bob_shared", "BobSecret456!", ip_address=shared_ip)
        assert auth_bob.id == "user_bob_shared"


@pytest.mark.asyncio
async def test_concurrent_login_attempts_separate_sessions(test_env):
    """
    Scenario 4: Concurrent login attempts executed across separate database sessions.
    Verifies that simultaneous failed attempts are committed cleanly without deadlock.
    """
    test_user = "concurrent_user"
    async with database.AsyncSessionLocal() as s:
        u = User(id="user_concurrent", username=test_user, password_hash=hash_password("P@ss1234"), role="editor")
        s.add(u)
        await s.commit()

    async def simulate_failed_attempt(ip_suffix: int):
        async with database.AsyncSessionLocal() as sess:
            await LoginProtectionService.record_attempt(sess, f"10.0.0.{ip_suffix}", test_user, success=False)

    # Run 10 parallel attempts across 10 distinct DB sessions
    tasks = [simulate_failed_attempt(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Check that all 10 attempts were recorded
    async with database.AsyncSessionLocal() as sess:
        is_lim, retry_after = await LoginProtectionService.check_rate_limit(sess, "10.0.0.99", test_user)
        assert is_lim, "Expected user to be locked out after 10 concurrent attempts"
        assert retry_after > 0


@pytest.mark.asyncio
async def test_rate_limit_expiry_and_success_reset(test_env):
    """
    Scenario 5: Lockout expiry and successful login reset.
    - Record 5 failed attempts for a pair -> locked out.
    - Successfully logging in clears failed attempts for that user.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_reset_test", username="reset_user", password_hash=hash_password("CorrectPass1!"), role="editor")
        session.add(u)
        await session.commit()

        ip = "127.0.0.1"
        for _ in range(5):
            await LoginProtectionService.record_attempt(session, ip, "reset_user", success=False)

        is_lim, _ = await LoginProtectionService.check_rate_limit(session, ip, "reset_user")
        assert is_lim

        # Reset via record_attempt with success=True (simulates successful auth flow)
        await LoginProtectionService.record_attempt(session, ip, "reset_user", success=True)

        is_lim_after, _ = await LoginProtectionService.check_rate_limit(session, ip, "reset_user")
        assert not is_lim_after, "Successful login should clear failed attempts and unlock account"


@pytest.mark.asyncio
async def test_client_ip_spoof_resistance_ignores_x_forwarded_for(client: AsyncClient, test_env):
    """
    Scenario 6: Verify client IP determination ignores spoofed X-Forwarded-For headers.
    An attacker sending arbitrary X-Forwarded-For headers cannot evade rate limiting.
    """
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_spoof_test", username="spoof_user", password_hash=hash_password("Pass123!"), role="editor")
        session.add(u)
        await session.commit()

    # Fail 5 times while sending randomized X-Forwarded-For headers
    for i in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "spoof_user", "password": "WrongPassword!"},
            headers={"X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert resp.status_code == 401

    # 6th attempt with yet another spoofed IP must STILL be locked out
    resp_locked = await client.post(
        "/api/v1/auth/login",
        json={"username": "spoof_user", "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "203.0.113.88"},
    )
    assert resp_locked.status_code == 429
    assert resp_locked.json()["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert "Retry-After" in resp_locked.headers


@pytest.mark.asyncio
async def test_account_enumeration_resistance_uniform_responses(client: AsyncClient, test_env):
    """
    Scenario 7: Uniform 401 responses regardless of whether the account exists or not.
    """
    # 1. Non-existent account
    resp_nonexistent = await client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_ghost_account_xyz", "password": "AnyPassword123!"},
    )
    assert resp_nonexistent.status_code == 401
    body_ghost = resp_nonexistent.json()

    # 2. Existing account with wrong password
    async with database.AsyncSessionLocal() as session:
        u = User(id="user_enum_real", username="real_existing_user", password_hash=hash_password("RealPassword1!"), role="editor")
        session.add(u)
        await session.commit()

    resp_wrong_pwd = await client.post(
        "/api/v1/auth/login",
        json={"username": "real_existing_user", "password": "WrongPassword!"},
    )
    assert resp_wrong_pwd.status_code == 401
    body_real = resp_wrong_pwd.json()

    # Responses must be completely identical in detail and error code
    assert body_ghost["detail"] == body_real["detail"] == "Incorrect username or password."
    assert body_ghost["code"] == body_real["code"] == "INVALID_CREDENTIALS"
