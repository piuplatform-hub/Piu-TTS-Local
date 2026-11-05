# Piu TTS Local

> Local-first AI Voice Studio for Vietnamese and Mandarin text-to-speech, voice cloning, durable jobs, and a React/Vite workstation.

## 1. Architecture

- `apps/server/`: FastAPI API, authentication, SQLite/SQLAlchemy data layer, job scheduler, and worker supervisor.
- `apps/web/`: React + TypeScript + Vite user interface.
- `engines/vieneu/`: VieNeu-TTS v3 Turbo for Vietnamese. It prefers PyTorch/CUDA and falls back to ONNX Runtime CPU.
- `engines/qwen3/`: Qwen3-TTS 0.6B CustomVoice for Mandarin on NVIDIA CUDA.
- `engines/mock/`: deterministic synthetic audio for contract and smoke tests only.
- `packages/engine_sdk/`: shared manifest, protocol, and worker client models.
- `alembic/`: database migrations. Runtime data and model weights should stay under `STUDIO_DATA_DIR`, outside the source tree.

## 2. Prerequisites

Use Windows PowerShell with:

- Python 3.10 or newer (3.10–3.12 are the tested worker range).
- Node.js and npm for the web client.
- NVIDIA driver/CUDA-compatible PyTorch for VieNeu or Qwen3 GPU inference.
- Git and enough disk space for model weights.

## 3. Installation

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r apps/server/requirements.txt
python -m pip install -e packages/engine_sdk

# Shared worker dependencies
python -m pip install numpy psutil soundfile soxr sea-g2p kaldi-native-fbank

# VieNeu GPU runtime (use `pip install vieneu` for CPU-only setup)
python -m pip install "vieneu[cuda]"

Copy-Item .env.example .env
alembic upgrade head
```

Set `SECRET_KEY` and `STUDIO_DATA_DIR` in `.env`. Keep `VIENEU_DEVICE=auto` for automatic CUDA detection; use `cpu` or `gpu` only for diagnostics. Qwen3 requires its own compatible `qwen_tts`/PyTorch environment if that engine is enabled.

## 4. Run locally

Start the API in one terminal:

```powershell
.venv\Scripts\Activate.ps1
python -m apps.server.src.main
```

Start the web client in another:

```powershell
npm ci --prefix apps/web
npm run dev --prefix apps/web -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. On first run, create the administrator account with the one-time token printed by the API or stored in `<STUDIO_DATA_DIR>\.bootstrap_token`; paste only the token value. API health is available at `http://127.0.0.1:8765/api/v1/health`.

## 5. Choosing an engine

- Vietnamese: choose **VieNeu-TTS v3 Turbo — GPU**. `auto` selects CUDA/PyTorch and falls back to ONNX/CPU when CUDA or model initialization is unavailable.
- Mandarin: choose **Qwen3-TTS — GPU** and a preset speaker.
- Mock: use only to validate UI/API plumbing without neural model weights.

The first VieNeu request can download weights and initialize CUDA. Later requests reuse the loaded model and should be much faster. `nvidia-smi` and the engine health endpoint confirm the actual device/backend.

## 6. Validation and troubleshooting

```powershell
python -m pytest -q
python -m pytest tests/unit -q
npm run build --prefix apps/web
python -c "import torch; print(torch.cuda.is_available())"
```

If only Mock appears, inspect the API log for missing `numpy`, `sea_g2p`, or `kaldi_native_fbank`. If a job remains stuck during speed adjustment, restart the worker and check the latest job record; the worker has a bounded fast speed fallback while its optional phase-vocoder path warms up. Never commit `.env`, databases, model weights, access tokens, or generated audio.
