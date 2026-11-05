"""
Contract & Compliance Tests for VieNeu-TTS Production Engine Adapter & Engine SDK
"""

import asyncio
import io
import os
from pathlib import Path
import subprocess
import wave
import pytest

from engine_sdk.manifest import EngineManifest, CapabilityEnum
from engine_sdk.protocol import SynthesisRequest
from engine_sdk.client import EngineWorkerClient

VIENEU_ENV_PYTHON = r"D:\AIVoiceStudioData\benchmarks\envs\vieneu_env\Scripts\python.exe"
REF_SAMPLE = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")


def test_vieneu_manifest_validation():
    manifest_path = os.path.join("engines", "vieneu", "engine.manifest.json")
    assert os.path.exists(manifest_path)
    manifest = EngineManifest.from_file(manifest_path)
    assert manifest.engine_id == "vieneu-tts"
    assert manifest.has_capability(CapabilityEnum.TEXT_TO_SPEECH)
    assert manifest.has_capability(CapabilityEnum.VOICE_CLONING)
    assert manifest.has_capability(CapabilityEnum.SPEAKER_SELECTION)
    assert "vi" in manifest.supported_languages
    assert manifest.default_sample_rate == 48000
    assert manifest.hardware_profile.default_device == "auto"
    assert set(manifest.hardware_profile.supported_devices) == {"cpu", "gpu"}


@pytest.mark.asyncio
async def test_vieneu_worker_lifecycle_and_contract():
    if not os.path.exists(VIENEU_ENV_PYTHON):
        pytest.skip(f"VieNeu environment not found at {VIENEU_ENV_PYTHON}")

    token = "vieneu-test-secret-token"
    worker_script = os.path.join("engines", "vieneu", "worker.py")

    proc = subprocess.Popen(
        [VIENEU_ENV_PYTHON, worker_script, "--port", "0", "--auth-token", token],
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

        assert port is not None, "Failed to capture port from VieNeu worker"
        base_url = f"http://127.0.0.1:{port}"

        # 1. Test unauthorized client
        unauth_client = EngineWorkerClient(base_url=base_url, auth_token="wrong-token")
        with pytest.raises(Exception):
            await unauth_client.get_health()

        # 2. Test authorized client
        client = EngineWorkerClient(base_url=base_url, auth_token=token, timeout=60.0)
        health = await client.get_health()
        assert health.status == "healthy"
        assert health.engine_id == "vieneu-tts"
        assert health.device in {"cpu", "gpu"}

        # 3. Test get_info
        info = await client.get_info()
        assert info.engine_id == "vieneu-tts"
        assert "text_to_speech" in info.capabilities
        assert "voice_cloning" in info.capabilities
        assert "vi" in info.supported_languages
        assert len(info.preset_voices) >= 20

        # 4. Test preset synthesis
        req = SynthesisRequest(
            job_id="test_job_vn_01",
            text="Xin chào, đây là bài kiểm thử tiếng Việt.",
            language="vi",
            voice_id="hai_dang",
            speed=1.0,
        )
        wav_bytes = await client.synthesize(req)
        assert len(wav_bytes) > 2000

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 48000
            assert wf.getnframes() > 10000

        # 5. Test voice cloning pipeline if reference audio is available
        if REF_SAMPLE.exists():
            clone_req = SynthesisRequest(
                job_id="test_job_vn_clone",
                text="Thử nghiệm đường ống nhân bản giọng nói.",
                language="vi",
                parameters={"ref_audio": str(REF_SAMPLE), "denoise": True},
            )
            clone_bytes = await client.synthesize(clone_req)
            assert len(clone_bytes) > 2000
            with wave.open(io.BytesIO(clone_bytes), "rb") as wf:
                assert wf.getframerate() == 48000

        # 6. Test RFC 9457 error on unsupported language
        err_req = SynthesisRequest(
            job_id="test_job_err",
            text="Hello world",
            language="en",
        )
        with pytest.raises(RuntimeError):
            await client.synthesize(err_req)

        # 7. Unload
        unload_res = await client.unload()
        assert unload_res.get("status") == "unloaded"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
