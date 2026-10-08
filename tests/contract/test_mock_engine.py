"""
Contract & Compliance Tests for Mock Engine Adapter & Engine SDK
"""

import asyncio
import os
import subprocess
import sys
import wave
import io
import pytest

from engine_sdk.manifest import EngineManifest, CapabilityEnum
from engine_sdk.protocol import SynthesisRequest
from engine_sdk.client import EngineWorkerClient


def test_manifest_validation():
    manifest_path = os.path.join("engines", "mock", "engine.manifest.json")
    assert os.path.exists(manifest_path)
    manifest = EngineManifest.from_file(manifest_path)
    assert manifest.engine_id == "mock-tts"
    assert manifest.has_capability(CapabilityEnum.TEXT_TO_SPEECH)
    assert manifest.has_capability(CapabilityEnum.SPEAKER_SELECTION)
    assert "vi" in manifest.supported_languages
    assert "zh" in manifest.supported_languages
    assert manifest.default_sample_rate == 44100


@pytest.mark.asyncio
async def test_mock_worker_lifecycle_and_contract():
    token = "test-secret-token-12345"
    worker_script = os.path.join("engines", "mock", "worker.py")

    # Start worker process with --port 0
    proc = subprocess.Popen(
        [sys.executable, worker_script, "--port", "0", "--auth-token", token],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    port = None
    try:
        # Read PORT from stdout
        for _ in range(50):
            line = proc.stdout.readline()
            if line.startswith("PORT:"):
                port = int(line.strip().split(":")[1])
                break
            await asyncio.sleep(0.05)

        assert port is not None, "Failed to capture ephemeral port from worker"
        base_url = f"http://127.0.0.1:{port}"

        # 1. Test unauthorized client
        unauth_client = EngineWorkerClient(base_url=base_url, auth_token="wrong-token")
        with pytest.raises(Exception):
            await unauth_client.get_health()

        # 2. Test authorized client
        client = EngineWorkerClient(base_url=base_url, auth_token=token)
        health = await client.get_health()
        assert health.status == "healthy"
        assert health.engine_id == "mock-tts"
        assert health.state == "ready"

        # 3. Test get_info
        info = await client.get_info()
        assert info.engine_id == "mock-tts"
        assert "text_to_speech" in info.capabilities
        assert len(info.preset_voices) >= 2

        # 4. Test valid synthesis
        req = SynthesisRequest(
            job_id="test_job_001",
            text="Xin chào, đây là bài kiểm tra hợp đồng âm thanh.",
            language="vi",
            voice_id="mock_vi_female_1",
            speed=1.0,
            sample_rate=44100,
        )
        wav_bytes = await client.synthesize(req)
        assert len(wav_bytes) > 1000

        # Verify WAV format integrity
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            assert wf.getnframes() > 4000

        # 5. Test RFC 9457 error on unsupported language
        err_req = SynthesisRequest(
            job_id="test_job_err",
            text="Hello world",
            language="unsupported_lang",
        )
        with pytest.raises(RuntimeError) as exc_info:
            await client.synthesize(err_req)
        assert "UNSUPPORTED_LANGUAGE" in str(exc_info.value)

        # 6. Test unload
        unload_res = await client.unload()
        assert unload_res.get("status") == "unloaded"

    finally:
        proc.terminate()
        proc.wait(timeout=3)
