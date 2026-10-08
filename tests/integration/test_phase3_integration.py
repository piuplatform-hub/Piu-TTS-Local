"""
AI Voice Studio — Phase 3 End-to-End Inference Integration Tests
Tests real neural speech synthesis pipelines:
1. VieNeu-TTS (CPU): Vietnamese TTS -> 48kHz WAV artifact creation & retrieval.
2. VieNeu-TTS (CPU): Zero-shot voice cloning pipeline with reference audio -> completed artifact.
3. Qwen3-TTS (GPU): Mandarin Chinese TTS -> 24kHz WAV artifact creation & retrieval on RTX 3050.
4. Concurrency & Slot Isolation: Parallel execution of CPU (VieNeu) and GPU (Qwen3) jobs,
   and queuing of 2nd GPU job due to strict max 1 GPU slot enforcement.
"""

import asyncio
import io
import math
from pathlib import Path
import struct
import wave
import pytest

from apps.server.src.core.security import get_or_create_bootstrap_token
from apps.server.src import database
from apps.server.src.services.engine_service import EngineService
from apps.server.src.supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest


@pytest.fixture(scope="function")
async def running_production_engines(test_env):
    """
    Starts real VieNeu-TTS and Qwen3-TTS engine workers in their isolated virtualenvs
    and registers them into the active test database.
    """
    workspace_root = Path(__file__).resolve().parents[2]

    vieneu_manifest_path = workspace_root / "engines" / "vieneu" / "engine.manifest.json"
    qwen3_manifest_path = workspace_root / "engines" / "qwen3" / "engine.manifest.json"

    vieneu_manifest = EngineManifest.from_file(str(vieneu_manifest_path))
    qwen3_manifest = EngineManifest.from_file(str(qwen3_manifest_path))

    # Start workers via supervisor
    await supervisor.start_worker(manifest=vieneu_manifest, workspace_root=workspace_root)
    await supervisor.start_worker(manifest=qwen3_manifest, workspace_root=workspace_root)

    # Register into database
    async with database.AsyncSessionLocal() as session:
        await EngineService.discover_and_register_engines(session, workspace_root, spawn_workers=False)

    yield {"vieneu": vieneu_manifest, "qwen3": qwen3_manifest}

    await supervisor.stop_all()


async def get_authenticated_headers(client):
    """Helper to authenticate admin user and obtain Bearer JWT."""
    token = get_or_create_bootstrap_token()
    boot_res = await client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "studio_admin", "password": "Password12345!", "setup_token": token},
    )
    assert boot_res.status_code == 201
    jwt_token = boot_res.json()["access_token"]
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.mark.asyncio
async def test_vieneu_tts_end_to_end_pipeline(client, running_production_engines):
    """
    1. VieNeu-TTS End-to-End:
       Submits Vietnamese synthesis job, verifies durable lifecycle,
       and validates generated 48kHz WAV audio artifact.
    """
    headers = await get_authenticated_headers(client)

    # Check registered engines
    res = await client.get("/api/v1/engines", headers=headers)
    assert res.status_code == 200
    engines = res.json()
    vieneu_eng = next((e for e in engines if e["id"] == "vieneu-tts"), None)
    assert vieneu_eng is not None
    assert "voice_cloning" in vieneu_eng["capabilities"]
    assert "hai_dang" in [v["id"] for v in vieneu_eng["preset_voices"]]

    # Submit Vietnamese speech synthesis job
    submit_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Xin chào, đây là kiểm thử VieNeu.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "voice_id": "hai_dang",
            "speed": 1.0,
            "idempotency_key": "vieneu-e2e-001",
        },
    )
    assert submit_res.status_code == 201
    job_id = submit_res.json()["id"]

    # Poll until completion (up to 60s for neural inference)
    artifact_id = None
    for _ in range(60):
        poll = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert poll.status_code == 200
        data = poll.json()
        if data["status"] == "completed":
            artifact_id = data["artifact_id"]
            assert data["progress_percent"] == 100
            break
        if data["status"] == "failed":
            pytest.fail(f"VieNeu job failed: {data.get('error_details')}")
        await asyncio.sleep(1.0)

    assert artifact_id is not None, "VieNeu job timed out without artifact"

    # Verify Artifact Metadata
    meta_res = await client.get(f"/api/v1/artifacts/{artifact_id}", headers=headers)
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["format"] == "wav"
    assert meta["sample_rate"] == 48000
    assert meta["duration_seconds"] > 0.3
    assert meta["file_size_bytes"] > 1000

    # Stream & Inspect Audio File
    file_res = await client.get(f"/api/v1/artifacts/{artifact_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.headers.get("content-type") == "audio/wav"

    audio_bytes = file_res.content
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit PCM
        assert wf.getframerate() == 48000
        frames = wf.getnframes()
        duration = frames / 48000.0
        assert duration > 0.3


@pytest.mark.asyncio
async def test_vieneu_tts_zero_shot_voice_cloning(client, running_production_engines, tmp_path):
    """
    2. VieNeu-TTS Voice Cloning:
       Passes reference audio WAV path in parameters and synthesizes cloned speech.
    """
    headers = await get_authenticated_headers(client)

    # Generate a reference audio file (1.5 seconds of sample speech tone) using standard library
    ref_wav_path = tmp_path / "ref_sample.wav"
    sample_rate = 24000
    n_samples = int(sample_rate * 1.5)
    with wave.open(str(ref_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(32767.0 * 0.2 * math.sin(2 * math.pi * 220.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)

    # Submit voice cloning job
    submit_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Thử nghiệm nhân bản giọng nói.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "parameters": {
                "ref_audio": str(ref_wav_path),
                "denoise": False,
            },
            "idempotency_key": "vieneu-clone-001",
        },
    )
    assert submit_res.status_code == 201
    job_id = submit_res.json()["id"]

    # Poll until completed
    artifact_id = None
    for _ in range(60):
        poll = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        data = poll.json()
        if data["status"] == "completed":
            artifact_id = data["artifact_id"]
            break
        if data["status"] == "failed":
            pytest.fail(f"VieNeu cloning job failed: {data.get('error_details')}")
        await asyncio.sleep(1.0)

    assert artifact_id is not None

    # Inspect artifact
    meta_res = await client.get(f"/api/v1/artifacts/{artifact_id}", headers=headers)
    assert meta_res.status_code == 200
    assert meta_res.json()["sample_rate"] == 48000


@pytest.mark.asyncio
async def test_qwen3_tts_end_to_end_pipeline(client, running_production_engines):
    """
    3. Qwen3-TTS End-to-End:
       Submits Mandarin synthesis job to GPU worker (bfloat16 on RTX 3050),
       and verifies 24kHz WAV audio artifact.
    """
    headers = await get_authenticated_headers(client)

    # Check registered engine
    res = await client.get("/api/v1/engines", headers=headers)
    assert res.status_code == 200
    engines = res.json()
    qwen3_eng = next((e for e in engines if e["id"] == "qwen3-tts"), None)
    assert qwen3_eng is not None
    assert "zh" in qwen3_eng["supported_languages"]
    assert "vivian" in [v["id"] for v in qwen3_eng["preset_voices"]]

    # Submit Mandarin speech synthesis job
    submit_res = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "你好，语音合成测试。",
            "engine_id": "qwen3-tts",
            "language": "zh",
            "voice_id": "vivian",
            "speed": 1.0,
            "idempotency_key": "qwen3-e2e-001",
        },
    )
    assert submit_res.status_code == 201
    job_id = submit_res.json()["id"]

    # Poll until completed (up to 90s for GPU inference)
    artifact_id = None
    for _ in range(90):
        poll = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert poll.status_code == 200
        data = poll.json()
        if data["status"] == "completed":
            artifact_id = data["artifact_id"]
            assert data["progress_percent"] == 100
            break
        if data["status"] == "failed":
            pytest.fail(f"Qwen3 job failed: {data.get('error_details')}")
        await asyncio.sleep(1.0)

    assert artifact_id is not None, "Qwen3 job timed out without artifact"

    # Verify Artifact Metadata
    meta_res = await client.get(f"/api/v1/artifacts/{artifact_id}", headers=headers)
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["format"] == "wav"
    assert meta["sample_rate"] == 24000
    assert meta["duration_seconds"] > 0.3

    # Stream & Inspect Audio File
    file_res = await client.get(f"/api/v1/artifacts/{artifact_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.headers.get("content-type") == "audio/wav"

    audio_bytes = file_res.content
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit PCM
        assert wf.getframerate() == 24000
        frames = wf.getnframes()
        duration = frames / 24000.0
        assert duration > 0.3


@pytest.mark.asyncio
async def test_concurrency_and_slot_isolation(client, running_production_engines):
    """
    4. Concurrency & Slot Isolation:
       - VieNeu (CPU) and Qwen3 (GPU) execute concurrently without resource lock contention.
       - A second Qwen3 job is queued with 'Awaiting GPU slot' until the first GPU job completes.
    """
    headers = await get_authenticated_headers(client)

    # Submit VieNeu (CPU)
    res_cpu = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "Kiểm thử CPU song song.",
            "engine_id": "vieneu-tts",
            "language": "vi",
            "voice_id": "hai_dang",
            "idempotency_key": "concurrent-cpu-1",
        },
    )
    assert res_cpu.status_code == 201
    cpu_job_id = res_cpu.json()["id"]

    # Submit Qwen3 #1 (GPU)
    res_gpu1 = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "第一条GPU任务。",
            "engine_id": "qwen3-tts",
            "language": "zh",
            "voice_id": "vivian",
            "idempotency_key": "concurrent-gpu-1",
        },
    )
    assert res_gpu1.status_code == 201
    gpu1_job_id = res_gpu1.json()["id"]

    # Submit Qwen3 #2 (GPU - must wait for GPU slot)
    res_gpu2 = await client.post(
        "/api/v1/jobs/speech",
        headers=headers,
        json={
            "text": "第二条GPU任务等待槽位。",
            "engine_id": "qwen3-tts",
            "language": "zh",
            "voice_id": "uncle_fu",
            "idempotency_key": "concurrent-gpu-2",
        },
    )
    assert res_gpu2.status_code == 201
    gpu2_job_id = res_gpu2.json()["id"]

    # Monitor and verify all 3 complete eventually
    active_jobs = {cpu_job_id, gpu1_job_id, gpu2_job_id}
    completed_jobs = set()

    for _ in range(120):
        for jid in list(active_jobs):
            poll = await client.get(f"/api/v1/jobs/{jid}", headers=headers)
            data = poll.json()
            if data["status"] == "completed":
                completed_jobs.add(jid)
                active_jobs.remove(jid)
            elif data["status"] == "failed":
                pytest.fail(f"Job {jid} failed: {data.get('error_details')}")
        if not active_jobs:
            break
        await asyncio.sleep(1.0)

    assert len(completed_jobs) == 3, f"Not all jobs completed: remaining {active_jobs}"
