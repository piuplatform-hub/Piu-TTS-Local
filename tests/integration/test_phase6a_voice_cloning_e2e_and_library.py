"""
Phase 6A-R1: Reusable Voice Library, Voice Profiles, Authenticated Reference Playback & Precedence Tests
"""

import io
import math
from pathlib import Path
import struct
import wave
import pytest
from httpx import AsyncClient

from apps.server.src import database
from apps.server.src.config import settings
from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src.models.job import JobRecord
from apps.server.src.models.voice_profile import VoiceProfileRecord
from apps.server.src.services.engine_service import EngineService
from sqlalchemy import select


@pytest.fixture(scope="function")
async def registered_engines_manifests(test_env):
    """Registers all engine manifests into test DB without spawning worker subprocesses."""
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


async def setup_two_users(client: AsyncClient):
    """Creates User A (creator) and User B (editor)."""
    token = get_or_create_bootstrap_token()
    boot = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "user_alpha_r1", "password": "Password12345!", "setup_token": token},
    )
    if boot.status_code == 201:
        tok_a = boot.json()["access_token"]
    else:
        log_a = await client.post("/api/v1/auth/login", json={"username": "user_alpha_r1", "password": "Password12345!"})
        tok_a = log_a.json()["access_token"]

    head_a = {"Authorization": f"Bearer {tok_a}"}

    # Create User B (editor role) via admin
    reg_b = await client.post(
        "/api/v1/auth/users",
        headers=head_a,
        json={"username": "user_bravo_r1", "password": "Password12345!", "role": "editor"},
    )
    assert reg_b.status_code in (201, 409)

    log_b = await client.post(
        "/api/v1/auth/login",
        json={"username": "user_bravo_r1", "password": "Password12345!"},
    )
    assert log_b.status_code == 200
    tok_b = log_b.json()["access_token"]
    head_b = {"Authorization": f"Bearer {tok_b}"}

    return head_a, head_b


@pytest.mark.asyncio
async def test_reference_audio_playback_and_authorization(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies authenticated reference audio playback endpoint:
    GET /api/v1/assets/reference-audio/{asset_id}/file
    - Valid user can stream audio bytes.
    - Query token is prohibited (CWE-598).
    - Other users receive HTTP 403 FORBIDDEN_ASSET_ACCESS.
    """
    headers_a, headers_b = await setup_two_users(client)

    # User A uploads reference audio
    wav_bytes = create_sample_wav(duration=2.5, sample_rate=24000)
    upload_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers_a,
        data={"voice_use_consent": "true"},
        files={"file": ("voice_actor_sample.wav", wav_bytes, "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["asset_id"]

    # 1. User A streams their own reference audio
    stream_res = await client.get(f"/api/v1/assets/reference-audio/{asset_id}/file", headers=headers_a)
    assert stream_res.status_code == 200
    assert stream_res.headers.get("Content-Type") == "audio/wav"
    assert len(stream_res.content) == len(wav_bytes)

    # 2. Query token is rejected with 400 (CWE-598)
    query_res = await client.get(f"/api/v1/assets/reference-audio/{asset_id}/file?token=some_token", headers=headers_a)
    assert query_res.status_code == 400
    assert query_res.json()["code"] == "QUERY_AUTH_PROHIBITED"

    # 3. User B tries to stream User A's reference audio -> 403
    forbidden_res = await client.get(f"/api/v1/assets/reference-audio/{asset_id}/file", headers=headers_b)
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["code"] == "FORBIDDEN_ASSET_ACCESS"


@pytest.mark.asyncio
async def test_reusable_voice_profiles_library(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies Reusable Voice Library in user-owned storage:
    - User A creates a VoiceProfile linked to an approved ReferenceAsset.
    - Profile is saved to SQLite AND persisted in settings.get_data_dir() / "voices" / user.id.
    - User B cannot access or use User A's voice profile.
    - Speech job can be submitted referencing the voice profile directly.
    """
    headers_a, headers_b = await setup_two_users(client)

    # User A uploads reference audio
    wav_bytes = create_sample_wav(duration=3.0, sample_rate=24000)
    upload_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers_a,
        data={"voice_use_consent": "true"},
        files={"file": ("profile_actor.wav", wav_bytes, "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["asset_id"]

    # 1. Create Voice Profile
    create_prof_res = await client.post(
        "/api/v1/voices/profiles",
        headers=headers_a,
        json={
            "name": "Giọng Thuyết Minh Truyền Cảm",
            "reference_asset_id": asset_id,
            "engine_id": "vieneu-tts",
            "description": "Giọng nữ truyền cảm cho podcast",
            "parameters": {
                "speed": 0.95,
                "temperature": 1.05,
                "top_p": 0.96,
                "top_k": 35,
                "repetition_penalty": 1.18,
                "denoise": True,
            },
        },
    )
    assert create_prof_res.status_code == 201
    prof_data = create_prof_res.json()
    profile_id = prof_data["id"]
    assert prof_data["name"] == "Giọng Thuyết Minh Truyền Cảm"

    # Verify on-disk file was created in user-isolated storage
    user_id = prof_data["user_id"]
    profile_file = settings.get_data_dir() / "voices" / user_id / f"{profile_id}.json"
    assert profile_file.exists(), f"Profile file was not persisted at {profile_file}"

    # 2. List Profiles
    list_res = await client.get("/api/v1/voices/profiles", headers=headers_a)
    assert list_res.status_code == 200
    profiles = list_res.json()
    assert any(p["id"] == profile_id for p in profiles)

    # 3. User B cannot access User A's profile
    unauth_get = await client.get(f"/api/v1/voices/profiles/{profile_id}", headers=headers_b)
    assert unauth_get.status_code == 403

    # 4. Synthesize speech using voice profile ID
    job_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Kiểm thử tạo âm thanh với hồ sơ giọng đã lưu.",
            "engine_id": "vieneu-tts",
            "voice_id": f"profile:{profile_id}",
            "language": "vi",
        },
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # Inspect job payload
    async with database.AsyncSessionLocal() as session:
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        job_rec = (await session.execute(stmt)).scalar_one()
        payload = job_rec.payload_data
        params = payload["parameters"]

        # Resolved from profile
        assert params.get("reference_asset_id") == asset_id
        assert "ref_audio" in params
        assert params.get("temperature") == 1.05
        assert params.get("repetition_penalty") == 1.18

    # 5. Delete Profile
    del_res = await client.delete(f"/api/v1/voices/profiles/{profile_id}", headers=headers_a)
    assert del_res.status_code == 200
    assert not profile_file.exists(), "Profile file should be removed on deletion"


@pytest.mark.asyncio
async def test_fail_closed_voice_cloning_and_no_silent_fallback(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies that invalid or missing references trigger explicit errors
    without any silent fallback to default preset:
    - Missing reference asset ID -> 404 REFERENCE_ASSET_NOT_FOUND
    - Reference asset lacking consent -> 400 VOICE_CONSENT_REQUIRED
    - Missing physical file on disk -> 404 REFERENCE_AUDIO_FILE_MISSING
    - Unsupported voice ID -> 422 UNSUPPORTED_VOICE
    """
    headers_a, _ = await setup_two_users(client)

    # 1. Non-existent reference asset ID -> 404
    job_404 = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Thử nghiệm reference asset không tồn tại.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "parameters": {"reference_asset_id": "non-existent-uuid-12345"},
        },
    )
    assert job_404.status_code == 404
    assert job_404.json()["code"] == "REFERENCE_ASSET_NOT_FOUND"

    # 2. Unsupported voice ID without cloning -> 422
    job_422 = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Thử nghiệm voice id sai.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "voice_id": "unknown_voice_persona",
        },
    )
    assert job_422.status_code == 422
    assert job_422.json()["code"] == "UNSUPPORTED_VOICE"

    # 3. Missing physical file on host disk -> 404
    wav_bytes = create_sample_wav(duration=1.5, sample_rate=24000)
    upload_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers_a,
        data={"voice_use_consent": "true"},
        files={"file": ("to_be_deleted.wav", wav_bytes, "audio/wav")},
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["asset_id"]

    # Delete physical file behind the scenes
    from apps.server.src.models.asset import ReferenceAssetRecord
    async with database.AsyncSessionLocal() as session:
        rec = await session.get(ReferenceAssetRecord, asset_id)
        Path(rec.file_path).unlink(missing_ok=True)

    job_disk_missing = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Thử nghiệm tệp bị xóa khỏi ổ đĩa.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "parameters": {"reference_asset_id": asset_id},
        },
    )
    assert job_disk_missing.status_code == 404
    assert job_disk_missing.json()["code"] == "REFERENCE_AUDIO_FILE_MISSING"


@pytest.mark.asyncio
async def test_segment_override_takes_precedence_over_character_default(client: AsyncClient, test_env, registered_engines_manifests):
    """
    Verifies precedence rule:
    Segment explicit parameters/voice MUST take precedence over Character default settings.
    - Character has Cloned Voice Reference A + temperature=0.9
    - Segment 1 inherits Character settings.
    - Segment 2 overrides with preset 'mai_anh' and temperature=0.5.
    - Verifies Segment 1 renders with Reference A, and Segment 2 renders with 'mai_anh' + temperature=0.5!
    """
    headers, _ = await setup_two_users(client)

    # Upload Reference A
    wav_bytes = create_sample_wav(duration=2.0, sample_rate=24000)
    up_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        data={"voice_use_consent": "true"},
        files={"file": ("char_ref_a.wav", wav_bytes, "audio/wav")},
    )
    assert up_res.status_code == 201
    ref_a_id = up_res.json()["asset_id"]

    # Create Dialogue Project
    proj_res = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Kiểm Tra Precedence Override", "project_type": "dialogue"},
    )
    proj_id = proj_res.json()["id"]

    # Create Character with Reference A
    char_res = await client.post(
        f"/api/v1/projects/{proj_id}/characters",
        headers=headers,
        json={
            "name": "Nhân Vật A",
            "avatar_color": "#06b6d4",
            "engine_id": "vieneu-tts",
            "voice_id": "hai_dang",
            "language": "vi",
            "parameters": {
                "reference_asset_id": ref_a_id,
                "temperature": 0.9,
                "speed": 1.0,
            },
        },
    )
    char_id = char_res.json()["id"]

    # Segment 1: Default inheritance
    seg1_res = await client.post(
        f"/api/v1/projects/{proj_id}/segments",
        headers=headers,
        json={
            "character_id": char_id,
            "text": "Đoạn một kế thừa trọn vẹn giọng nhân bản của nhân vật.",
            "sequence_order": 0,
        },
    )
    seg1_id = seg1_res.json()["id"]

    # Segment 2: Explicit Segment Override (Overrides voice to 'mai_anh', temperature=0.5)
    seg2_res = await client.post(
        f"/api/v1/projects/{proj_id}/segments",
        headers=headers,
        json={
            "character_id": char_id,
            "text": "Đoạn hai cố tình ghi đè bằng giọng Mai Anh.",
            "sequence_order": 1,
            "voice_id": "mai_anh",
            "parameters": {"temperature": 0.5},
        },
    )
    seg2_id = seg2_res.json()["id"]

    # Render Segment 1
    r1 = await client.post(f"/api/v1/projects/{proj_id}/segments/{seg1_id}/render", headers=headers)
    assert r1.status_code == 200
    job1_id = r1.json()["last_job_id"]

    # Render Segment 2
    r2 = await client.post(f"/api/v1/projects/{proj_id}/segments/{seg2_id}/render", headers=headers)
    assert r2.status_code == 200
    job2_id = r2.json()["last_job_id"]

    # Query both jobs
    async with database.AsyncSessionLocal() as session:
        j1 = (await session.execute(select(JobRecord).where(JobRecord.id == job1_id))).scalar_one()
        j2 = (await session.execute(select(JobRecord).where(JobRecord.id == job2_id))).scalar_one()

        # Job 1 inherited Character's Reference A
        p1 = j1.payload_data["parameters"]
        assert p1.get("reference_asset_id") == ref_a_id
        assert p1.get("temperature") == 0.9

        # Job 2 OVERRODE with Mai Anh and temperature=0.5
        assert j2.payload_data.get("voice_id") == "mai_anh"
        p2 = j2.payload_data["parameters"]
        assert p2.get("temperature") == 0.5
