"""
Rigorous Security & Authorization Verification Tests
Covers:
1. Concurrent Onboarding Race Condition (Atomic Bootstrap)
2. Token TTL Expiration
3. Multi-User RBAC & Cross-User Data Access Isolation (Jobs & Artifacts)
"""

import asyncio
import json
import time
import pytest
from apps.server.src.core.security import get_or_create_bootstrap_token, get_bootstrap_token_file


@pytest.mark.asyncio
async def test_concurrent_onboarding_race_condition(client):
    """
    Simulates two competing bootstrap requests sent concurrently.
    Verifies that exactly ONE admin user is created and the other request fails.
    """
    token = get_or_create_bootstrap_token()

    req_a = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_alpha", "password": "PasswordAlpha123!", "setup_token": token},
    )
    req_b = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_beta", "password": "PasswordBeta123!", "setup_token": token},
    )

    # Execute both requests concurrently
    res_a, res_b = await asyncio.gather(req_a, req_b, return_exceptions=False)

    # Exactly one must succeed with 201 Created
    status_codes = [res_a.status_code, res_b.status_code]
    assert 201 in status_codes, f"Expected at least one success, got {status_codes}"
    assert status_codes.count(201) == 1, f"Expected exactly one 201 Created, got {status_codes}"

    # The failing request must be rejected with 401 or 409
    losing_res = res_a if res_b.status_code == 201 else res_b
    assert losing_res.status_code in (401, 409)

    # System status confirms single user
    res_status = await client.get("/api/v1/auth/status")
    assert res_status.json()["total_users"] == 1
    assert res_status.json()["needs_onboarding"] is False


@pytest.mark.asyncio
async def test_bootstrap_token_ttl_expiration(client):
    """
    Verifies that an expired bootstrap token is rejected.
    """
    # Create an expired token by writing past expiration time
    token_file = get_bootstrap_token_file()
    expired_token = "0123456789abcdef0123456789abcdef0123456789abcdef"
    token_file.write_text(
        json.dumps({
            "token": expired_token,
            "created_at": time.time() - 3600,
            "expires_at": time.time() - 100,  # Expired
        }),
        encoding="utf-8",
    )

    res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_test", "password": "Password123!", "setup_token": expired_token},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_SETUP_TOKEN"


@pytest.mark.asyncio
async def test_multi_user_cross_authorization_isolation(client, running_mock_engine):
    """
    Verifies that User B (editor) CANNOT access User A's jobs, artifacts, or cancel jobs,
    and cannot provision users.
    """
    # 1. Bootstrap Admin
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "main_admin", "password": "AdminPassword123!", "setup_token": token},
    )
    assert boot_res.status_code == 201
    admin_token = boot_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin provisions User A (editor) and User B (editor)
    user_a_res = await client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "alice", "password": "AlicePassword123!", "role": "editor"},
    )
    assert user_a_res.status_code == 201

    user_b_res = await client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "bob", "password": "BobPassword123!", "role": "editor"},
    )
    assert user_b_res.status_code == 201

    # 3. Login as User A
    login_a = await client.post("/api/v1/auth/login", json={"username": "alice", "password": "AlicePassword123!"})
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 4. Login as User B
    login_b = await client.post("/api/v1/auth/login", json={"username": "bob", "password": "BobPassword123!"})
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 5. User A submits a TTS Job
    job_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Nội dung riêng tư của Alice",
            "engine_id": "mock-tts",
            "language": "vi",
        },
    )
    assert job_res.status_code == 201
    job_a_id = job_res.json()["id"]

    # Poll until completed to obtain artifact
    artifact_a_id = None
    for _ in range(30):
        p = await client.get(f"/api/v1/jobs/{job_a_id}", headers=headers_a)
        if p.json()["status"] == "completed":
            artifact_a_id = p.json()["artifact_id"]
            break
        await asyncio.sleep(0.1)

    assert artifact_a_id is not None

    # 6. User B attempts unauthorized operations on Alice's resources:
    # 6a. User B views Alice's Job Details -> 403 Forbidden
    unauth_job = await client.get(f"/api/v1/jobs/{job_a_id}", headers=headers_b)
    assert unauth_job.status_code == 403
    assert unauth_job.json()["code"] == "FORBIDDEN_JOB_ACCESS"

    # 6b. User B cancels Alice's Job -> 403 Forbidden
    unauth_cancel = await client.post(f"/api/v1/jobs/{job_a_id}/cancel", headers=headers_b)
    assert unauth_cancel.status_code == 403
    assert unauth_cancel.json()["code"] == "FORBIDDEN_JOB_ACCESS"

    # 6c. User B views Alice's Artifact Metadata -> 403 Forbidden
    unauth_meta = await client.get(f"/api/v1/artifacts/{artifact_a_id}", headers=headers_b)
    assert unauth_meta.status_code == 403
    assert unauth_meta.json()["code"] == "FORBIDDEN_ARTIFACT_ACCESS"

    # 6d. User B downloads/streams Alice's Artifact File -> 403 Forbidden
    unauth_file = await client.get(f"/api/v1/artifacts/{artifact_a_id}/file", headers=headers_b)
    assert unauth_file.status_code == 403
    assert unauth_file.json()["code"] == "FORBIDDEN_ARTIFACT_ACCESS"

    # 6e. User B tries to provision a user -> 403 Forbidden (Non-admin)
    unauth_create = await client.post(
        "/api/v1/auth/users",
        headers=headers_b,
        json={"username": "eve", "password": "EvePassword123!", "role": "viewer"},
    )
    assert unauth_create.status_code == 403
    assert unauth_create.json()["code"] == "FORBIDDEN_USER_CREATION"

    # 6f. User B lists jobs -> Alice's job must NOT appear
    b_jobs = await client.get("/api/v1/jobs", headers=headers_b)
    assert b_jobs.status_code == 200
    b_job_ids = [j["id"] for j in b_jobs.json()]
    assert job_a_id not in b_job_ids

    # 7. Admin CAN access Alice's resources (authorized admin oversight)
    admin_view = await client.get(f"/api/v1/jobs/{job_a_id}", headers=admin_headers)
    assert admin_view.status_code == 200
