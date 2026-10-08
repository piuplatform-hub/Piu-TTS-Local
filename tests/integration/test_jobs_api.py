"""
Integration Tests for TTS Jobs, Artifacts, and Idempotency
"""

import asyncio
import pytest
from apps.server.src.core.security import get_or_create_bootstrap_token


@pytest.mark.asyncio
async def test_tts_job_lifecycle_and_artifact(client, running_mock_engine):
    # 1. Onboard initial admin
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "studio_admin", "password": "Password12345!", "setup_token": token},
    )
    assert boot_res.status_code == 201
    jwt_token = boot_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # 2. Check engine registry
    engines_res = await client.get("/api/v1/engines", headers=headers)
    assert engines_res.status_code == 200
    engines = engines_res.json()
    assert len(engines) >= 1
    mock_eng = next(e for e in engines if e["id"] == "mock-tts")
    assert "text_to_speech" in mock_eng["capabilities"]
    assert "vi" in mock_eng["supported_languages"]
    assert len(mock_eng["preset_voices"]) >= 2

    # 3. Submit valid speech job
    submit_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Chào mừng đến với AI Voice Studio Phase 1",
            "engine_id": "mock-tts",
            "language": "vi",
            "voice_id": "vi-female-1",
            "speed": 1.0,
            "idempotency_key": "test-key-001",
        },
    )
    assert submit_res.status_code == 201
    job_data = submit_res.json()
    job_id = job_data["id"]
    assert job_data["status"] in ("queued", "running", "completed")

    # 4. Poll job status until completed
    artifact_id = None
    for _ in range(30):
        poll_res = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        if poll_data["status"] == "completed":
            artifact_id = poll_data["artifact_id"]
            assert poll_data["progress_percent"] == 100
            break
        if poll_data["status"] == "failed":
            pytest.fail(f"Job failed unexpectedly: {poll_data}")
        await asyncio.sleep(0.1)

    assert artifact_id is not None, "Job did not complete within timeout"

    # 5. Fetch Artifact Metadata
    meta_res = await client.get(f"/api/v1/artifacts/{artifact_id}", headers=headers)
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["id"] == artifact_id
    assert meta["format"] == "wav"
    assert meta["sample_rate"] == 44100
    assert meta["duration_seconds"] > 0
    assert meta["file_size_bytes"] > 0

    # 6. Fetch Audio File Stream
    file_res = await client.get(f"/api/v1/artifacts/{artifact_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert "audio/wav" in file_res.headers.get("content-type", "")
    audio_bytes = file_res.content
    assert audio_bytes[:4] == b"RIFF"
    assert b"WAVE" in audio_bytes[:16]

    # 7. Test Idempotency: Resubmitting with same key returns identical job
    idem_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Khác nội dung nhưng cùng key",
            "engine_id": "mock-tts",
            "language": "vi",
            "idempotency_key": "test-key-001",
        },
    )
    assert idem_res.status_code in (200, 201)
    assert idem_res.json()["id"] == job_id

    # 8. Test Error Handling: Unsupported Language -> RFC 9457 422
    err_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Bonjour",
            "engine_id": "mock-tts",
            "language": "fr",
        },
    )
    assert err_res.status_code == 422
    err_json = err_res.json()
    assert err_json["code"] == "UNSUPPORTED_LANGUAGE"

    # 9. Test Error Handling: Non-existent Engine -> RFC 9457 400
    err_eng = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Test",
            "engine_id": "non-existent-engine",
            "language": "vi",
        },
    )
    assert err_eng.status_code == 400
    assert err_eng.json()["code"] == "ENGINE_NOT_FOUND"
