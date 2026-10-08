# ENGINE ADAPTER SDK & PLUGIN CONTRACT SPECIFICATION (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-PLG-001-R1  
**Status:** REVISED ARCHITECTURE (R1) — AWAITING PHASE 1 AUTHORIZATION  
**Date:** October 2026  

---

## 1. Engine SDK Design Principles (Revision R1)

1. **Zero Hardcoded Engine Logic:** Core business logic has no dependency on specific engine names. It interacts solely through the **Engine Adapter SDK Contract v1.0**.
2. **Capability-Driven Contracts:** No universal assumptions about features (e.g. pitch, speed, or voice cloning). An engine declares only what it supports.
3. **Security & Trusted Plugin Policy:** Running an external Python script can execute arbitrary code. The platform strictly enforces that **only Admin-approved, signature/hash-verified adapters** may be registered and executed. Untrusted third-party code execution is strictly prohibited.
4. **Distinct Metadata Separation:** Complete decoupling of:
   * **Engine Metadata:** Adapter code, author, license, SDK version.
   * **Model Metadata:** Checkpoint weights, file hashes, download sources, VRAM requirements.
   * **Voice Metadata:** Preset speakers, custom cloned speaker profiles, consent records.
   * **Runtime Configuration:** Environment path, execution device (CPU/CUDA), port, timeouts.

---

## 2. Standardized Plugin Manifest (`engine.manifest.json` v1.0)

Every engine directory must provide an `engine.manifest.json` validated against JSON Schema:

```json
{
  "$schema": "https://ai-voice-studio.local/schemas/engine.manifest.v1.json",
  "manifest_version": "1.0",
  "engine_id": "vieneu-tts",
  "name": "VieNeu-TTS v3 Turbo",
  "version": "3.2.0",
  "author": "pnnbao97 (Adapted for AI Voice Studio)",
  "license": "Apache-2.0",
  "integrity": {
    "entrypoint_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "capabilities": [
    "text_to_speech",
    "voice_cloning",
    "speaker_selection"
  ],
  "supported_languages": ["vi", "en"],
  "default_sample_rate": 48000,
  "runtime": {
    "entrypoint": "engines/vieneu/worker.py",
    "python_version_min": "3.10",
    "python_version_max": "3.12",
    "virtualenv_path": "engines/vieneu/.venv"
  },
  "hardware_profile": {
    "supported_devices": ["cpu", "cuda"],
    "default_device": "cpu",
    "estimated_vram_mb": 0,
    "estimated_ram_mb": 1500
  },
  "parameters_schema": {
    "speed": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 2.0,
      "default": 1.0,
      "description": "Speech rate multiplier"
    }
  }
}
```

---

## 3. Worker Lifecycle & State Machine

A worker process transitions through distinct operational states tracked by the supervisor:

```mermaid
stateDiagram-v2
    [*] --> UNLOADED : Worker Process Spawned
    UNLOADED --> LOADING : POST /load (Model weights loading)
    LOADING --> READY : Weights in Memory / VRAM
    LOADING --> ERROR : Load Failed (Missing weights / OOM)
    
    READY --> INFERRING : POST /synthesize or POST /clone
    INFERRING --> READY : Inference Finished
    INFERRING --> READY : POST /cancel (Aborted)
    INFERRING --> ERROR : CUDA OOM / Internal Segfault
    
    READY --> UNLOADING : POST /unload
    UNLOADING --> UNLOADED : Memory / VRAM Freed
    
    ERROR --> UNLOADED : Reset / Cleanup
    UNLOADED --> [*] : Process Shutdown
```

---

## 4. Worker HTTP Protocol & Standardized Error Contracts

Workers expose an authenticated HTTP service on loopback (`127.0.0.1:<ephemeral_port>`). Every request must include the header `X-Worker-Token: <secret>`.

### 4.1 Protocol Endpoints

| Endpoint | Method | Input | Output | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | None | `{ status, state, device, memory_mb }` | Liveness & state probe. |
| `/info` | GET | None | Manifest metadata & preset voices. | Capability discovery. |
| `/load` | POST | `{ model_id, device }` | `{ status, loaded_at }` | Explicitly load model weights. |
| `/synthesize` | POST | JSON (text, voice_id, params) | `audio/wav` binary payload | Synthesize speech. |
| `/clone` | POST | Multipart (text, audio file) | `audio/wav` binary payload | Clone voice from sample. |
| `/cancel` | POST | `{ job_id }` | `{ status: "cancelled" }` | Abort ongoing generation. |
| `/unload` | POST | None | `{ status: "unloaded", freed_mb }` | Free VRAM/RAM immediately. |

### 4.2 Standardized Error Contract (RFC 9457 Format)

When an error occurs, the worker responds with standard HTTP status codes and a structured JSON body adhering to **RFC 9457**:

```json
{
  "type": "https://ai-voice-studio.local/errors/cuda-out-of-memory",
  "title": "CUDA Out of Memory",
  "status": 507,
  "detail": "Failed to allocate 1.2 GiB on GPU 0. Free memory was only 450 MiB.",
  "instance": "/jobs/job_948a7f21",
  "code": "CUDA_OOM",
  "retryable": true,
  "backoff_seconds": 5
}
```

#### Standard Error Codes:
* `MODEL_NOT_FOUND` (404): Checkpoint files missing on disk.
* `INVALID_INPUT_PARAMS` (400): Text exceeds length limit or parameters violate schema.
* `UNSUPPORTED_LANGUAGE` (422): Engine does not support the requested language token.
* `CUDA_OOM` (507): GPU VRAM exhausted during synthesis.
* `INFERENCE_TIMEOUT` (504): Synthesis exceeded max execution limit.
* `WORKER_INTERNAL_ERROR` (500): Unhandled Python exception.

---

## 5. Security & Trusted Plugin Verification Policy

To prevent arbitrary code execution on the host machine:
1. **Administrative Authorization Gate:** Newly discovered directories in `engines/` are marked `PENDING_APPROVAL` in `studio.db`. The core server will not launch a worker until an Admin explicitly approves it via `/api/v1/engines/{id}/approve`.
2. **File Checksum Verification:** During approval, the supervisor computes the SHA-256 hash of the entrypoint file (`worker.py`) and requirements. If the file is altered on disk, the supervisor halts startup and alerts the administrator.
3. **Isolated User Rights:** Workers inherit the host user permissions but are strictly forbidden from binding to network interfaces other than `127.0.0.1`.

---

## 6. Contract Verification Suite (`tests/contract/`)

The plugin contract is verified via an automated Pytest test harness before any engine is integrated into production:

```python
# Conceptual contract test ensuring engine compliance
def test_engine_contract_compliance(authenticated_worker_client):
    # 1. Verify health & state
    health = authenticated_worker_client.get("/health").json()
    assert health["status"] == "healthy"
    assert health["state"] in ["UNLOADED", "READY"]

    # 2. Verify RFC 9457 error on invalid language
    err = authenticated_worker_client.post("/synthesize", json={
        "job_id": "test_err_01",
        "text": "Hello",
        "language": "invalid_lang_code"
    })
    assert err.status_code == 422
    assert err.json()["code"] == "UNSUPPORTED_LANGUAGE"

    # 3. Verify synthesis output
    res = authenticated_worker_client.post("/synthesize", json={
        "job_id": "test_ok_01",
        "text": "Test speech synthesis.",
        "language": "en"
    })
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "audio/wav"
```
