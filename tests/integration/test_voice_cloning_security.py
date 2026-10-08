"""
Voice Cloning Security & Engine Parameter Contract Enforcement Tests
Verifies:
1. Upload requires explicit voice-use consent (400 if False).
2. Upload rejects non-WAV / corrupt audio formats (422).
3. Upload enforces duration limits (0.5s - 30s) (422).
4. Cross-user isolation: User B cannot use User A's reference audio asset (403 Forbidden).
5. Path traversal / Host filesystem path injection is strictly prohibited (422).
6. Voice cloning is rejected on engines without cloning capability (Qwen3, Mock) (422).
7. Arbitrary unsupported parameter keys are rejected (422).
8. Unsupported voice_id is rejected (422).
9. Speaker parameter enum validation for Qwen3 (422).
"""

import io
import math
from pathlib import Path
import struct
import wave
import pytest

from apps.server.src import database
from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src.services.engine_service import EngineService
from engine_sdk.manifest import EngineManifest


def create_sample_wav(duration: float = 2.0, sample_rate: int = 24000) -> bytes:
    """Generates standard in-memory WAV bytes."""
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


async def setup_two_users(client):
    """Sets up Admin (User A) and standard user (User B)."""
    # 1. Onboard initial admin
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "user_a", "password": "Password12345!", "setup_token": token},
    )
    assert boot_res.status_code == 201
    jwt_a = boot_res.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {jwt_a}"}

    # 2. Register User B
    reg_res = await client.post(
        "/api/v1/auth/users",
        headers=headers_a,
        json={"username": "user_b", "password": "Password12345!", "role": "editor"},
    )
    assert reg_res.status_code == 201

    login_b = await client.post(
        "/api/v1/auth/login",
        json={"username": "user_b", "password": "Password12345!"},
    )
    assert login_b.status_code == 200
    jwt_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {jwt_b}"}

    return headers_a, headers_b


@pytest.fixture(scope="function")
async def registered_engines_manifests(test_env):
    """Registers all engine manifests into test DB without starting heavy neural workers."""
    workspace_root = Path(__file__).resolve().parents[2]
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(session, workspace_root, spawn_workers=False)


@pytest.mark.asyncio
async def test_voice_cloning_upload_requires_explicit_consent(client, test_env):
    """Upload must fail with 400 if voice_use_consent is false."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_test", "password": "Password12345!", "setup_token": token},
    )
    headers = {"Authorization": f"Bearer {boot_res.json()['access_token']}"}

    wav_bytes = create_sample_wav(2.0)
    res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        files={"file": ("sample.wav", wav_bytes, "audio/wav")},
        data={"voice_use_consent": "false"},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "VOICE_CONSENT_REQUIRED"


@pytest.mark.asyncio
async def test_voice_cloning_upload_invalid_format(client, test_env):
    """Upload must fail with 422 if file is not a valid RIFF/WAVE PCM."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_test", "password": "Password12345!", "setup_token": token},
    )
    headers = {"Authorization": f"Bearer {boot_res.json()['access_token']}"}

    fake_bytes = b"NOT_A_REAL_WAV_HEADER_FAKE_DATA_HERE"
    res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        files={"file": ("fake.wav", fake_bytes, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_AUDIO_FORMAT"


@pytest.mark.asyncio
async def test_voice_cloning_upload_duration_limits(client, test_env):
    """Upload must reject audio longer than 30s or shorter than 0.5s."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin_test", "password": "Password12345!", "setup_token": token},
    )
    headers = {"Authorization": f"Bearer {boot_res.json()['access_token']}"}

    # Too short (< 0.5s)
    short_bytes = create_sample_wav(0.2)
    res_short = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        files={"file": ("short.wav", short_bytes, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert res_short.status_code == 422
    assert res_short.json()["code"] == "AUDIO_TOO_SHORT"

    # Too long (> 30s)
    long_bytes = create_sample_wav(35.0)
    res_long = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers,
        files={"file": ("long.wav", long_bytes, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert res_long.status_code == 422
    assert res_long.json()["code"] == "AUDIO_TOO_LONG"


@pytest.mark.asyncio
async def test_voice_cloning_cross_user_isolation(client, test_env, registered_engines_manifests):
    """User B cannot submit job with User A's reference audio asset (403 Forbidden)."""
    headers_a, headers_b = await setup_two_users(client)

    # User A uploads asset
    wav_bytes = create_sample_wav(2.0)
    upload_res = await client.post(
        "/api/v1/assets/reference-audio",
        headers=headers_a,
        files={"file": ("user_a_sample.wav", wav_bytes, "audio/wav")},
        data={"voice_use_consent": "true"},
    )
    assert upload_res.status_code == 201
    asset_id_a = upload_res.json()["asset_id"]

    # User B tries to get metadata for User A's asset
    meta_res = await client.get(f"/api/v1/assets/reference-audio/{asset_id_a}", headers=headers_b)
    assert meta_res.status_code == 403
    assert meta_res.json()["code"] == "FORBIDDEN_ASSET_ACCESS"

    # User B tries to use User A's asset in a speech job
    job_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_b,
        json={
            "text": "Kiểm tra cách ly người dùng.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "parameters": {
                "reference_asset_id": asset_id_a,
            },
        },
    )
    assert job_res.status_code == 403
    assert job_res.json()["code"] == "FORBIDDEN_ASSET_ACCESS"


@pytest.mark.asyncio
async def test_filesystem_path_injection_prohibited(client, test_env, registered_engines_manifests):
    """Client cannot supply host filesystem paths directly in parameters (422 prohibited)."""
    headers_a, _ = await setup_two_users(client)

    # Test arbitrary absolute and relative path injection
    malicious_paths = [
        "C:\\Windows\\System32\\calc.exe",
        "/etc/passwd",
        "../../sensitive.wav",
        "D:/AIVoiceStudioData/sample.wav",
    ]

    for p in malicious_paths:
        job_res = await client.post(
            "/api/v1/jobs/speech",
            headers=headers_a,
            json={
                "text": "Kiểm tra path injection.",
                "engine_id": "vieneu-tts",
                "language": "vi",
                "parameters": {
                    "ref_audio": p,
                },
            },
        )
        assert job_res.status_code == 422
        assert job_res.json()["code"] == "FILESYSTEM_PATH_INJECTION_PROHIBITED"


@pytest.mark.asyncio
async def test_voice_cloning_rejected_on_unsupported_engine(client, test_env, registered_engines_manifests):
    """Engines without voice_cloning capability (Qwen3, Mock) must reject cloning parameters with 422."""
    headers_a, _ = await setup_two_users(client)

    # 1. Qwen3-TTS (Mandarin CustomVoice without cloning)
    res_qwen = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "测试克隆拒绝",
            "engine_id": "qwen3-tts",
            "language": "zh",
            "parameters": {
                "reference_asset_id": "some-random-id",
            },
        },
    )
    assert res_qwen.status_code == 422
    assert res_qwen.json()["code"] == "VOICE_CLONING_NOT_SUPPORTED"

    # 2. Mock-TTS (Contract mock without cloning)
    res_mock = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Kiểm tra mock từ chối cloning",
            "engine_id": "mock-tts",
            "language": "vi",
            "parameters": {
                "reference_asset_id": "some-random-id",
            },
        },
    )
    assert res_mock.status_code == 422
    assert res_mock.json()["code"] == "VOICE_CLONING_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_arbitrary_unsupported_parameters_rejected(client, test_env, registered_engines_manifests):
    """Unknown parameters outside declared parameters_schema must be rejected with 422."""
    headers_a, _ = await setup_two_users(client)

    res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Kiểm tra tham số không xác định",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "parameters": {
                "unsupported_hacker_param": 12345,
            },
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "UNSUPPORTED_PARAMETER"


@pytest.mark.asyncio
async def test_unsupported_voice_rejected(client, test_env, registered_engines_manifests):
    """Requesting a voice_id not in engine preset voices must fail with 422."""
    headers_a, _ = await setup_two_users(client)

    res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "Kiểm tra giọng không tồn tại",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "voice_id": "non_existent_voice_xyz",
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "UNSUPPORTED_VOICE"


@pytest.mark.asyncio
async def test_qwen3_speaker_enum_validation(client, test_env, registered_engines_manifests):
    """Passing an invalid speaker name to Qwen3 must be rejected with 422."""
    headers_a, _ = await setup_two_users(client)

    res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers_a,
        json={
            "text": "测试无效角色",
            "engine_id": "qwen3-tts",
            "language": "zh",
            "parameters": {
                "speaker": "invalid_speaker_name",
            },
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_PARAMETER_VALUE"
