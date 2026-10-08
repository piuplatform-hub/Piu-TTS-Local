"""
Contract & Compliance Tests for Qwen3-TTS Production Engine Adapter & Engine SDK
"""

import asyncio
import io
import os
import subprocess
import wave
import pytest

from engine_sdk.manifest import EngineManifest, CapabilityEnum
from engine_sdk.protocol import SynthesisRequest
from engine_sdk.client import EngineWorkerClient

QWEN3_ENV_PYTHON = r"D:\AIVoiceStudioData\benchmarks\envs\qwen3_env\Scripts\python.exe"


def test_qwen3_manifest_validation():
    manifest_path = os.path.join("engines", "qwen3", "engine.manifest.json")
    assert os.path.exists(manifest_path)
    manifest = EngineManifest.from_file(manifest_path)
    assert manifest.engine_id == "qwen3-tts"
    assert manifest.has_capability(CapabilityEnum.TEXT_TO_SPEECH)
    assert manifest.has_capability(CapabilityEnum.SPEAKER_SELECTION)
    # Strictly NO voice cloning capability for CustomVoice
    assert not manifest.has_capability(CapabilityEnum.VOICE_CLONING)
    assert "zh" in manifest.supported_languages
    assert manifest.default_sample_rate == 24000
    assert manifest.hardware_profile.default_device == "gpu"


@pytest.mark.asyncio
async def test_qwen3_worker_lifecycle_and_contract():
    if not os.path.exists(QWEN3_ENV_PYTHON):
        pytest.skip(f"Qwen3 environment not found at {QWEN3_ENV_PYTHON}")

    token = "qwen3-test-secret-token"
    worker_script = os.path.join("engines", "qwen3", "worker.py")

    proc = subprocess.Popen(
        [QWEN3_ENV_PYTHON, worker_script, "--port", "0", "--auth-token", token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    port = None
    try:
        # Read ephemeral port
        for _ in range(50):
            line = proc.stdout.readline()
            if line.startswith("PORT:"):
                port = int(line.strip().split(":")[1])
                break
            await asyncio.sleep(0.05)

        assert port is not None, "Failed to capture port from Qwen3 worker"
        base_url = f"http://127.0.0.1:{port}"

        # 1. Test unauthorized client
        unauth_client = EngineWorkerClient(base_url=base_url, auth_token="wrong-token")
        with pytest.raises(Exception):
            await unauth_client.get_health()

        # 2. Test authorized client
        client = EngineWorkerClient(base_url=base_url, auth_token=token, timeout=90.0)
        health = await client.get_health()
        assert health.status == "healthy"
        assert health.engine_id == "qwen3-tts"
        assert health.device == "gpu"

        # 3. Test get_info
        info = await client.get_info()
        assert info.engine_id == "qwen3-tts"
        assert "text_to_speech" in info.capabilities
        assert "voice_cloning" not in info.capabilities
        assert "zh" in info.supported_languages
        assert len(info.preset_voices) == 9

        # 4. Test Mandarin speech synthesis
        req = SynthesisRequest(
            job_id="test_job_zh_01",
            text="你好，测试语音合成。",
            language="zh",
            voice_id="vivian",
            speed=1.0,
        )
        wav_bytes = await client.synthesize(req)
        assert len(wav_bytes) > 2000

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
            assert wf.getnframes() > 10000

        # 5. Test RFC 9457 error on unsupported language
        err_req = SynthesisRequest(
            job_id="test_job_err",
            text="Xin chào",
            language="vi",
        )
        with pytest.raises(RuntimeError):
            await client.synthesize(err_req)

        # 6. Unload
        unload_res = await client.unload()
        assert unload_res.get("status") == "unloaded"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
