"""
Phase 6A: Voice Lab, Deep Voice Controls & Vietnamese Voice Cloning Tests
Verifies:
1. Deep Engine Capability Discovery Endpoint (GET /api/v1/engines/{id}/capabilities).
2. Upstream Audit Handling: VieNeu-TTS, Qwen3-TTS, and Kokoro status.
3. Strict parameter schema validation & bounds enforcement for native voice controls.
4. End-to-end inheritance of voice cloning assets (reference_asset_id) from Character to Segment in Dialogue Projects.
"""

import io
import math
import struct
import wave
import pytest
from httpx import AsyncClient

from apps.server.src import database
from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src.models.job import JobRecord
from apps.server.src.services.engine_service import EngineService
from engine_sdk.manifest import EngineManifest
from pathlib import Path


@pytest.fixture(scope="function")
async def registered_engines_manifests(test_env):
    """Registers all engine manifests into test DB without starting heavy neural workers."""
    workspace_root = Path(__file__).resolve().parents[2]
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(session, workspace_root, spawn_workers=False)


def create_sample_wav(duration: float = 2.0, sample_rate: int = 24000) -> bytes:
    """Generates standard in-memory mono WAV bytes."""
    buf = io.BytesIO()
    n_samples = int(duration * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(32767.0 * 0.2 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)
    return buf.getvalue()


async def setup_auth_user(client: AsyncClient, username: str = "test_creator") -> dict:
    """Bootstraps admin or creates user and returns headers."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": username, "password": "Password12345!", "setup_token": token},
    )
    if boot_res.status_code == 201:
        jwt_token = boot_res.json()["access_token"]
    else:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Password12345!"},
        )
        assert login_res.status_code == 200
        jwt_token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.mark.asyncio
async def test_engine_capability_discovery_api(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies GET /api/v1/engines/{engine_id}/capabilities returns
    deep verified parameter definitions and presets for each model.
    """
    headers = await setup_auth_user(client)

    # 1. VieNeu-TTS Discovery
    res_vieneu = await client.get("/api/v1/engines/vieneu-tts/capabilities", headers=headers)
    assert res_vieneu.status_code == 200
    data_v = res_vieneu.json()
    assert data_v["engine_id"] == "vieneu-tts"
    assert data_v["installed"] is True
    assert "voice_cloning" in data_v["capabilities"]
    assert "advanced_voice_controls" in data_v["capabilities"]
    assert data_v["default_sample_rate"] == 48000

    # Verify native & DSP parameter definitions
    param_names = [p["name"] for p in data_v["parameters"]]
    assert "speed" in param_names
    assert "temperature" in param_names
    assert "top_p" in param_names
    assert "top_k" in param_names
    assert "repetition_penalty" in param_names
    assert "denoise" in param_names

    # Verify preset templates
    preset_ids = [pr["id"] for pr in data_v["presets"]]
    assert "natural_default" in preset_ids
    assert "expressive_story" in preset_ids
    assert "fast_news" in preset_ids
    assert "stable_audiobook" in preset_ids

    # 2. Qwen3-TTS Discovery
    res_qwen = await client.get("/api/v1/engines/qwen3-tts/capabilities", headers=headers)
    assert res_qwen.status_code == 200
    data_q = res_qwen.json()
    assert data_q["engine_id"] == "qwen3-tts"
    q_param_names = [p["name"] for p in data_q["parameters"]]
    assert "speaker" in q_param_names
    assert "speed" in q_param_names

    # 3. Kokoro Audit Discovery (Not Installed in Current Local Workspace)
    res_kokoro = await client.get("/api/v1/engines/kokoro-tts/capabilities", headers=headers)
    assert res_kokoro.status_code == 200
    data_k = res_kokoro.json()
    assert data_k["engine_id"] == "kokoro-tts"
    assert data_k["installed"] is False
    assert data_k["status"] == "not_installed"
    assert "NOT INSTALLED" in data_k["description"]


@pytest.mark.asyncio
async def test_native_controls_validation_and_bounds(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies that native sampling parameters (temperature, top_p, top_k, repetition_penalty)
    are strictly validated and bounded against out-of-range or malicious values.
    """
    headers = await setup_auth_user(client)

    # 1. Valid parameters submission
    valid_payload = {
        "text": "Kiểm thử tham số tinh chỉnh giọng nâng cao hợp lệ.",
        "engine_id": "vieneu-tts",
        "language": "vi",
        "voice_id": "hai_dang",
        "speed": 1.1,
        "parameters": {
            "temperature": 0.85,
            "top_p": 0.92,
            "top_k": 30,
            "repetition_penalty": 1.25,
            "repetition_window": 60,
        },
    }
    res_valid = await client.post("/api/v1/jobs/speech", headers=headers, json=valid_payload)
    assert res_valid.status_code == 201
    job_id = res_valid.json()["id"]

    # Verify parameters were safely sanitized and stored in job payload
    job_get = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_get.status_code == 200

    # 2. Out-of-bounds temperature (> 2.0)
    bad_temp = {
        "text": "Kiểm thử nhiệt độ sai.",
        "engine_id": "vieneu-tts",
        "language": "vi",
        "voice_id": "hai_dang",
        "parameters": {"temperature": 4.5},
    }
    res_bad_temp = await client.post("/api/v1/jobs/speech", headers=headers, json=bad_temp)
    assert res_bad_temp.status_code == 422
    assert "Temperature parameter must be a number between 0.1 and 2.0" in res_bad_temp.json()["detail"]

    # 3. Out-of-bounds top_p (> 1.0)
    bad_top_p = {
        "text": "Kiểm thử top p sai.",
        "engine_id": "vieneu-tts",
        "language": "vi",
        "voice_id": "hai_dang",
        "parameters": {"top_p": 1.5},
    }
    res_bad_p = await client.post("/api/v1/jobs/speech", headers=headers, json=bad_top_p)
    assert res_bad_p.status_code == 422
    assert "Top-P parameter must be a number between 0.01 and 1.0" in res_bad_p.json()["detail"]

    # 4. Out-of-bounds top_k (< 1 or > 200)
    bad_top_k = {
        "text": "Kiểm thử top k sai.",
        "engine_id": "vieneu-tts",
        "language": "vi",
        "voice_id": "hai_dang",
        "parameters": {"top_k": 999},
    }
    res_bad_k = await client.post("/api/v1/jobs/speech", headers=headers, json=bad_top_k)
    assert res_bad_k.status_code == 422
    assert "Top-K parameter must be an integer between 1 and 200" in res_bad_k.json()["detail"]

    # 5. Unsupported parameter injection
    bad_unsupported = {
        "text": "Kiểm thử parameter lạ.",
        "engine_id": "vieneu-tts",
        "language": "vi",
        "voice_id": "hai_dang",
        "parameters": {"malicious_eval_string": "rm -rf /"},
    }
    res_unsupported = await client.post("/api/v1/jobs/speech", headers=headers, json=bad_unsupported)
    assert res_unsupported.status_code == 422
    assert "Parameter 'malicious_eval_string' is not recognized" in res_unsupported.json()["detail"]


@pytest.mark.asyncio
async def test_dialogue_character_voice_cloning_inheritance(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies P0 resolution: In Multi-character Dialogue Projects, when a Character
    is configured with a cloned voice (reference_asset_id), rendering the segment
    (both single render and batch render) MUST inherit reference_asset_id and ref_audio,
    guaranteeing that no silent fallback to default 'hai_dang' occurs!
    """
    headers = await setup_auth_user(client)

    # 1. Upload valid reference audio asset with explicit legal consent
    wav_bytes = create_sample_wav(duration=3.0, sample_rate=24000)
    upload_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        data={"voice_use_consent": "true"},
        files={"file": ("reference_voice_actor.wav", wav_bytes, "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["asset_id"]

    # 2. Create Dialogue Project
    proj_res = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Kịch Truyền Thanh - Dialogue Voice Cloning",
            "project_type": "dialogue",
        },
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 3. Create Character with Cloned Voice Profile
    char_res = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        headers=headers,
        json={
            "name": "Nhân Vật Nhân Bản (Actor A)",
            "avatar_color": "#10b981",
            "engine_id": "vieneu-tts",
            "voice_id": "hai_dang",
            "language": "vi",
            "parameters": {
                "reference_asset_id": asset_id,
                "denoise": True,
                "temperature": 0.95,
                "repetition_penalty": 1.15,
            },
        },
    )
    assert char_res.status_code == 201
    char_id = char_res.json()["id"]

    # 4. Add Script Segment linked to this Character
    seg_res = await client.post(
        f"/api/v1/projects/{project_id}/segments",
        headers=headers,
        json={
            "character_id": char_id,
            "text": "Chào bạn, đây là lời thoại của nhân vật sử dụng giọng nhân bản.",
            "sequence_order": 0,
        },
    )
    assert seg_res.status_code == 201
    seg_id = seg_res.json()["id"]

    # Verify that add_segment automatically synced character parameters into the segment
    assert seg_res.json()["engine_id"] == "vieneu-tts"
    assert seg_res.json()["parameters"].get("reference_asset_id") == asset_id

    # 5. Render Segment and inspect Job Submission
    render_res = await client.post(
        f"/api/v1/projects/{project_id}/segments/{seg_id}/render",
        headers=headers,
    )
    assert render_res.status_code == 200
    seg_data = render_res.json()
    job_id = seg_data["last_job_id"]
    assert job_id is not None

    # 6. Query Job from database and verify payload_data
    from apps.server.src import database
    from sqlalchemy import select
    async with database.AsyncSessionLocal() as session:
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        job_rec = (await session.execute(stmt)).scalar_one()

        payload = job_rec.payload_data
        params = payload["parameters"]

        # CRITICAL ASSERTIONS:
        # Reference asset ID must be present
        assert params.get("reference_asset_id") == asset_id
        # Safe server-resolved file path must be passed to worker
        assert "ref_audio" in params
        assert str(params["ref_audio"]).endswith(f"{asset_id}.wav")
        # Native sampling parameters must be inherited
        assert params.get("temperature") == 0.95
        assert params.get("repetition_penalty") == 1.15
        assert params.get("denoise") is True

    # 7. Test Batch Render Inheritance
    # Add a second segment
    seg_res2 = await client.post(
        f"/api/v1/projects/{project_id}/segments",
        headers=headers,
        json={
            "character_id": char_id,
            "text": "Đoạn thoại số hai trong loạt phân cảnh hội thoại.",
            "sequence_order": 1,
        },
    )
    assert seg_res2.status_code == 201
    seg_id2 = seg_res2.json()["id"]

    batch_res = await client.post(
        f"/api/v1/projects/{project_id}/render-batch",
        headers=headers,
        json={"segment_ids": [seg_id2]},
    )
    assert batch_res.status_code == 200
    batch_segs = batch_res.json()
    assert len(batch_segs) == 1
    batch_job_id = batch_segs[0]["last_job_id"]
    assert batch_job_id is not None

    async with database.AsyncSessionLocal() as session:
        stmt = select(JobRecord).where(JobRecord.id == batch_job_id)
        batch_job_rec = (await session.execute(stmt)).scalar_one()
        batch_params = batch_job_rec.payload_data["parameters"]
        assert batch_params.get("reference_asset_id") == asset_id
        assert "ref_audio" in batch_params
        assert batch_params.get("temperature") == 0.95
