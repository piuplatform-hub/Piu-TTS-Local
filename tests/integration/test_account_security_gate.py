"""
Integration Tests for Gate A Account Security:
1. Deactivated accounts (is_active = 0) cannot log in (403 Forbidden).
2. Existing JWT tokens issued before deactivation are immediately rejected (401 Unauthorized).
3. Password change revokes existing JWT sessions (token_version increment).
4. Hardcoded QA credentials cannot authenticate when disabled.
5. Admin account credentials rejection of QA test passwords.
6. Transactional deactivation preserves SQLite foreign keys and data integrity.
"""

import pytest
import sqlite3
from sqlalchemy import select, update
from apps.server.src import database
from apps.server.src.models.user import User
from apps.server.src.models.project import ProjectRecord
from apps.server.src.core.security import hash_password, create_access_token
from apps.server.src.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_deactivated_account_blocks_new_login(client):
    """
    Verifies that is_active = 0 immediately rejects login attempts with 403 Forbidden.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(
            id="test_disabled_user_1",
            username="disabled_user",
            password_hash=hash_password("SecurePassword123!"),
            role="editor",
            is_active=False,
        )
        session.add(user)
        await session.commit()

    # Attempt login with correct credentials
    res = await client.post(
        "/api/v1/auth/login",
        json={"username": "disabled_user", "password": "SecurePassword123!"},
    )
    assert res.status_code == 403
    data = res.json()
    assert data["code"] == "ACCOUNT_DISABLED"
    assert "deactivated" in data["detail"].lower()


@pytest.mark.asyncio
async def test_deactivated_account_blocks_previously_issued_jwt(client):
    """
    Verifies that is_active = 0 immediately invalidates existing JWT sessions.
    The user can authenticate initially, but subsequent API calls fail once is_active=False.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(
            id="test_active_to_disabled_user",
            username="active_then_disabled",
            password_hash=hash_password("ActivePass123!"),
            role="editor",
            is_active=True,
            token_version=1,
        )
        session.add(user)
        await session.commit()

    # 1. Login and get token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "active_then_disabled", "password": "ActivePass123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 2. Verify token works
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "active_then_disabled"

    # 3. Deactivate user in database
    async with database.AsyncSessionLocal() as session:
        stmt = update(User).where(User.username == "active_then_disabled").values(is_active=False)
        await session.execute(stmt)
        await session.commit()

    # 4. Immediate subsequent API call with same token MUST be rejected
    rejected_res = await client.get("/api/v1/auth/me", headers=headers)
    assert rejected_res.status_code == 401
    err = rejected_res.json()
    assert err["code"] == "USER_INACTIVE"


@pytest.mark.asyncio
async def test_password_change_revokes_token_version(client):
    """
    Verifies that changing a password increments token_version and invalidates previous JWTs.
    """
    async with database.AsyncSessionLocal() as session:
        user = User(
            id="test_pw_change_user",
            username="pw_changer",
            password_hash=hash_password("OldPassword123!"),
            role="editor",
            is_active=True,
            token_version=1,
        )
        session.add(user)
        await session.commit()

    # 1. Login with old password -> Token 1
    res1 = await client.post(
        "/api/v1/auth/login",
        json={"username": "pw_changer", "password": "OldPassword123!"},
    )
    assert res1.status_code == 200
    token1 = res1.json()["access_token"]

    headers1 = {"Authorization": f"Bearer {token1}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers1)
    assert me_res.status_code == 200

    # 2. Change password
    change_res = await client.post(
        "/api/v1/auth/change-password",
        headers=headers1,
        json={
            "old_password": "OldPassword123!",
            "new_password": "NewSecretPassword456!",
        },
    )
    assert change_res.status_code == 200

    # 3. Old token MUST now be rejected due to token_version mismatch
    revoked_res = await client.get("/api/v1/auth/me", headers=headers1)
    assert revoked_res.status_code == 401
    assert revoked_res.json()["code"] == "TOKEN_REVOKED"

    # 4. Login with old password fails
    fail_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "pw_changer", "password": "OldPassword123!"},
    )
    assert fail_res.status_code == 401

    # 5. Login with new password succeeds and produces valid new token
    res2 = await client.post(
        "/api/v1/auth/login",
        json={"username": "pw_changer", "password": "NewSecretPassword456!"},
    )
    assert res2.status_code == 200
    token2 = res2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    ok_res = await client.get("/api/v1/auth/me", headers=headers2)
    assert ok_res.status_code == 200


@pytest.mark.asyncio
async def test_disabled_qa_credentials_cannot_authenticate(client):
    """
    Verifies that all 7 QA test accounts with known passwords cannot authenticate
    once their accounts have is_active = 0.
    """
    known_qa_accounts = [
        ("victim_account", "ValidPassword123!"),
        ("alice_shared", "AliceSecret123!"),
        ("bob_shared", "BobSecret456!"),
        ("concurrent_user", "P@ss1234"),
        ("reset_user", "CorrectPass1!"),
        ("spoof_user", "Pass123!"),
        ("real_existing_user", "RealPassword1!"),
    ]

    # Seed accounts as deactivated
    async with database.AsyncSessionLocal() as session:
        for uname, pwd in known_qa_accounts:
            u = User(
                id=f"id_{uname}",
                username=uname,
                password_hash=hash_password(pwd),
                role="editor",
                is_active=False,
            )
            session.add(u)
        await session.commit()

    # Attempt to authenticate every single QA account with its known password
    for uname, pwd in known_qa_accounts:
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": uname, "password": pwd},
        )
        assert res.status_code == 403, f"Expected 403 for disabled {uname}, got {res.status_code}"
        assert res.json()["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_transactional_deactivation_preserves_fk_integrity(client):
    """
    Verifies that updating is_active = 0 across users in a transaction does NOT
    break SQLite foreign key constraints or orphan project records.
    """
    async with database.AsyncSessionLocal() as session:
        # Create user
        u = User(
            id="qa_owner_user",
            username="qa_owner",
            password_hash=hash_password("OwnerPass123!"),
            role="editor",
            is_active=True,
        )
        session.add(u)
        await session.flush()

        # Create project belonging to user
        p = ProjectRecord(
            id="qa_proj_1",
            user_id="qa_owner_user",
            title="QA Project to Preserve",
            project_type="narration",
        )
        session.add(p)
        await session.commit()

    # Perform transactional update (exact same SQL logic planned for Gate A)
    async with database.AsyncSessionLocal() as session:
        stmt = update(User).where(User.username == "qa_owner").values(is_active=False)
        await session.execute(stmt)
        await session.commit()

    # Verify user is deactivated but still exists
    async with database.AsyncSessionLocal() as session:
        u_check = (await session.execute(select(User).where(User.username == "qa_owner"))).scalar_one()
        assert u_check.is_active is False

        p_check = (await session.execute(select(ProjectRecord).where(ProjectRecord.user_id == "qa_owner_user"))).scalar_one()
        assert p_check.title == "QA Project to Preserve"
