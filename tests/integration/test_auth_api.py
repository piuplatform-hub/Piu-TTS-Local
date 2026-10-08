"""
Integration Tests for Authentication, Onboarding, and JWT Security
"""

import pytest
from apps.server.src.core.security import get_or_create_bootstrap_token


@pytest.mark.asyncio
async def test_auth_onboarding_lifecycle(client):
    # 1. System starts uninitialized
    res = await client.get("/api/v1/auth/status")
    assert res.status_code == 200
    data = res.json()
    assert data["needs_onboarding"] is True
    assert data["total_users"] == 0

    # 2. Get local bootstrap token
    bootstrap_token = get_or_create_bootstrap_token()
    assert len(bootstrap_token) >= 16

    # 3. Attempt bootstrap with invalid token fails
    res_fail = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "username": "admin",
            "password": "CorrectPassword123!",
            "setup_token": "invalid_token_1234567890",
        },
    )
    assert res_fail.status_code == 401
    fail_data = res_fail.json()
    assert fail_data["code"] == "INVALID_SETUP_TOKEN"

    # 4. Attempt bootstrap with valid token succeeds
    res_ok = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "username": "admin",
            "password": "CorrectPassword123!",
            "setup_token": bootstrap_token,
        },
    )
    assert res_ok.status_code == 201
    auth_data = res_ok.json()
    assert "access_token" in auth_data
    assert auth_data["user"]["username"] == "admin"
    assert auth_data["user"]["role"] == "admin"
    token = auth_data["access_token"]

    # 5. Subsequent status shows onboarding is closed
    res_status = await client.get("/api/v1/auth/status")
    assert res_status.status_code == 200
    assert res_status.json()["needs_onboarding"] is False
    assert res_status.json()["total_users"] == 1

    # 6. Duplicate bootstrap attempt is rejected with 409 Conflict
    res_dup = await client.post(
        "/api/v1/auth/bootstrap",
        json={
            "username": "hacker",
            "password": "AnotherPassword123!",
            "setup_token": bootstrap_token,
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["code"] == "ALREADY_INITIALIZED"

    # 7. Login with invalid password fails
    res_bad_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "WrongPassword!"},
    )
    assert res_bad_login.status_code == 401
    assert res_bad_login.json()["code"] == "INVALID_CREDENTIALS"

    # 8. Login with valid credentials succeeds
    res_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "CorrectPassword123!"},
    )
    assert res_login.status_code == 200
    login_token = res_login.json()["access_token"]

    # 9. Access protected profile with Bearer token
    res_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_token}"},
    )
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "admin"

    # 10. Access protected profile without token is rejected
    res_unauth = await client.get("/api/v1/auth/me")
    assert res_unauth.status_code == 401
    assert res_unauth.json()["code"] == "UNAUTHORIZED"
