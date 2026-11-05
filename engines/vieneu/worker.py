"""
AI Voice Studio — VieNeu-TTS v3 Turbo Worker Process
Runs isolated in Python 3.12 (vieneu_env) with automatic CUDA/PyTorch
selection and an ONNX Runtime CPU fallback.
Exposes loopback HTTP interface compliant with Engine Adapter SDK v1.0.
"""

import argparse
import gc
from http.server import HTTPServer, BaseHTTPRequestHandler
import io
import json
import os
from pathlib import Path
from socketserver import ThreadingMixIn
import sys
import threading
import time

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure Hugging Face cache points to configured location
os.environ["HF_HOME"] = r"D:\AIVoiceStudioData\benchmarks\models\huggingface"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import numpy as np
import psutil
import soundfile as sf

ENGINE_ID = "vieneu-tts"

PRESET_VOICE_CATALOG = [
    {"id": "hai_dang", "name": "Hải Đăng", "gender": "male", "desc": "Bắc · Phong cách tự nhiên"},
    {"id": "mai_anh", "name": "Mai Anh", "gender": "female", "desc": "Bắc · Phong cách tin tức"},
    {"id": "truc_ly", "name": "Trúc Ly", "gender": "female", "desc": "Bắc · Phong cách tự nhiên"},
    {"id": "thien_minh", "name": "Thiện Minh", "gender": "male", "desc": "Bắc · Phong cách kể chuyện"},
    {"id": "thuy_dung", "name": "Thùy Dung", "gender": "female", "desc": "Nam · Phong cách tin tức"},
    {"id": "thien_tam_duc", "name": "Thiền Tâm Đức", "gender": "male", "desc": "Bắc · Phong cách kể chuyện"},
    {"id": "ngoc_huyen", "name": "Ngọc Huyền", "gender": "female", "desc": "Bắc · Giọng đọc tự nhiên"},
    {"id": "quang_son", "name": "Quang Sơn", "gender": "male", "desc": "Trung · Phong cách tự nhiên"},
    {"id": "ngoc_tran", "name": "Ngọc Trân", "gender": "female", "desc": "Trung · Phong cách tự nhiên"},
    {"id": "minh_duc", "name": "Minh Đức", "gender": "male", "desc": "Bắc · Phong cách tin tức"},
    {"id": "thai_son", "name": "Thái Sơn", "gender": "male", "desc": "Nam · Phong cách kể chuyện"},
    {"id": "xuan_vinh", "name": "Xuân Vĩnh", "gender": "male", "desc": "Bắc · Phong cách tự nhiên"},
    {"id": "ngoc_linh", "name": "Ngọc Linh", "gender": "female", "desc": "Bắc · Phong cách kể chuyện"},
    {"id": "doan_trang", "name": "Đoan Trang", "gender": "female", "desc": "Bắc · Phong cách tự nhiên"},
    {"id": "thuc_doan", "name": "Thục Đoan", "gender": "female", "desc": "Nam · Phong cách kể chuyện"},
    {"id": "minh_triet", "name": "Minh Triết", "gender": "male", "desc": "Nam · Phong cách tin tức"},
    {"id": "my_duyen", "name": "Mỹ Duyên", "gender": "female", "desc": "Nam · Phong cách đọc truyện"},
    {"id": "quynh_anh", "name": "Quỳnh Anh", "gender": "female", "desc": "Bắc · Phong cách đọc truyện"},
    {"id": "duc_tri", "name": "Đức Trí", "gender": "male", "desc": "Nam · Phong cách đọc truyện"},
    {"id": "kim_thanh", "name": "Kim Thanh", "gender": "female", "desc": "Nam · Phong cách đọc truyện"},
    {"id": "adam", "name": "Adam", "gender": "male", "desc": "Nam · Giọng đọc tự nhiên"},
    {"id": "quoc_tuan", "name": "Quốc Tuấn", "gender": "male", "desc": "Bắc · Phong cách tự nhiên"},
]

VOICE_MAP = {v["id"]: v["name"] for v in PRESET_VOICE_CATALOG}
VOICE_MAP.update({v["name"].lower(): v["name"] for v in PRESET_VOICE_CATALOG})


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class VieNeuModelManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._state = "unloaded"
        self._device = self._detect_device()
        self._backend = "pytorch" if self._device == "gpu" else "onnx"
        self._fallback_reason = None

    @staticmethod
    def _cuda_available() -> bool:
        """Return whether the worker environment can initialize CUDA safely."""
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    @classmethod
    def _detect_device(cls) -> str:
        """
        Resolve the requested device before loading model weights.

        ``auto`` is the default. Explicit ``cpu`` is useful for diagnostics,
        while explicit ``gpu`` still falls back to CPU when CUDA is absent.
        """
        requested = os.environ.get("VIENEU_DEVICE", "auto").strip().lower()
        if requested in {"cpu", "onnx"}:
            return "cpu"
        if requested in {"gpu", "cuda"}:
            return "gpu" if cls._cuda_available() else "cpu"
        return "gpu" if cls._cuda_available() else "cpu"

    @staticmethod
    def _load_cpu_model(vieneu_factory):
        """Force the upstream SDK's ONNX backend for a CPU fallback."""
        return vieneu_factory(backend="onnx")

    def get_model(self):
        with self._lock:
            if self._model is None:
                self._state = "loading"
                try:
                    from vieneu import Vieneu

                    if self._device == "gpu":
                        try:
                            # VieNeu auto-selects its PyTorch/CUDA backend when
                            # CUDA is available in the worker environment.
                            self._model = Vieneu()
                            self._backend = "pytorch"
                        except Exception as gpu_exc:
                            # A visible CUDA device is not sufficient proof that
                            # model initialization will succeed (driver, VRAM,
                            # or torch wheel problems can still occur).
                            self._fallback_reason = str(gpu_exc)
                            try:
                                self._model = self._load_cpu_model(Vieneu)
                            except Exception as cpu_exc:
                                raise RuntimeError(
                                    f"GPU initialization failed: {gpu_exc}; "
                                    f"CPU fallback failed: {cpu_exc}"
                                ) from cpu_exc
                            self._device = "cpu"
                            self._backend = "onnx"
                    else:
                        self._model = self._load_cpu_model(Vieneu)
                        self._backend = "onnx"
                    self._state = "ready"
                except Exception as exc:
                    self._state = "error"
                    raise RuntimeError(f"Failed to initialize VieNeu-TTS model: {exc}")
            return self._model

    def unload(self):
        with self._lock:
            if self._model is not None:
                self._state = "unloading"
                try:
                    if hasattr(self._model, "close"):
                        self._model.close()
                except Exception:
                    pass
                self._model = None
                gc.collect()
            self._state = "unloaded"

    @property
    def state(self) -> str:
        return self._state

    @property
    def device(self) -> str:
        return self._device

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def fallback_reason(self):
        return self._fallback_reason


model_manager = VieNeuModelManager()
_time_stretch_ready = threading.Event()
_time_stretch_started = False
_time_stretch_start_lock = threading.Lock()


def _warm_time_stretch() -> None:
    """Compile librosa's optional phase-vocoder path in the background."""
    try:
        import librosa

        warm_audio = np.zeros(4096, dtype=np.float32)
        librosa.effects.time_stretch(warm_audio, rate=0.95)
    except Exception:
        # Speed control remains best-effort; synthesis itself must not fail
        # because optional DSP warm-up is unavailable.
        pass
    finally:
        _time_stretch_ready.set()


def _start_time_stretch_warmup() -> None:
    global _time_stretch_started
    with _time_stretch_start_lock:
        if _time_stretch_started:
            return
        _time_stretch_started = True
        threading.Thread(target=_warm_time_stretch, daemon=True, name="vieneu-dsp-warmup").start()


def _fast_speed_adjust(audio_array: np.ndarray, speed: float) -> np.ndarray:
    """Bounded NumPy fallback while the optional phase-vocoder path warms up."""
    target_len = max(1, int(round(len(audio_array) / float(speed))))
    source_x = np.arange(len(audio_array), dtype=np.float32)
    target_x = np.linspace(0, max(0, len(audio_array) - 1), target_len, dtype=np.float32)
    return np.interp(target_x, source_x, audio_array).astype(np.float32, copy=False)


class VieNeuWorkerHandler(BaseHTTPRequestHandler):
    auth_token: str = ""

    def log_message(self, format, *args):
        # Silence HTTP access log to keep supervisor console clean
        pass

    def _check_auth(self) -> bool:
        token = self.headers.get("X-Worker-Token")
        if not token or token != self.auth_token:
            self._send_rfc9457_error(
                status=401,
                title="Unauthorized Worker Access",
                code="UNAUTHORIZED",
                detail="Missing or invalid X-Worker-Token header.",
            )
            return False
        return True

    def _send_rfc9457_error(self, status: int, title: str, code: str, detail: str, retryable: bool = False):
        err_body = json.dumps({
            "type": f"https://ai-voice-studio.local/errors/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
            "retryable": retryable,
            "instance": self.path,
        }).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/problem+json")
        self.send_header("Content-Length", str(len(err_body)))
        self.end_headers()
        self.wfile.write(err_body)

    def do_GET(self):
        if not self._check_auth():
            return

        if self.path == "/health":
            process = psutil.Process()
            rss_mb = int(process.memory_info().rss / (1024 * 1024))
            resp = json.dumps({
                "status": "healthy",
                "engine_id": ENGINE_ID,
                "state": model_manager.state if model_manager.state != "unloaded" else "ready",
                "device": model_manager.device,
                "backend": model_manager.backend,
                "fallback_reason": model_manager.fallback_reason,
                "memory_mb": rss_mb,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        elif self.path == "/info":
            voices = [
                {
                    "id": v["id"],
                    "name": v["name"],
                    "language": "vi",
                    "gender": v["gender"],
                    "description": v["desc"],
                }
                for v in PRESET_VOICE_CATALOG
            ]
            resp = json.dumps({
                "engine_id": ENGINE_ID,
                "name": "VieNeu-TTS v3 Turbo",
                "version": "3.8.3",
                "capabilities": ["text_to_speech", "voice_cloning", "speaker_selection"],
                "supported_languages": ["vi"],
                "preset_voices": voices,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        else:
            self._send_rfc9457_error(404, "Endpoint Not Found", "NOT_FOUND", f"Unknown endpoint {self.path}")

    def do_POST(self):
        if not self._check_auth():
            return

        if self.path == "/synthesize":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_rfc9457_error(400, "Empty Request", "INVALID_PAYLOAD", "Request body is empty.")
                return

            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except Exception as e:
                self._send_rfc9457_error(400, "Malformed JSON", "INVALID_JSON", str(e))
                return

            text = body.get("text", "").strip()
            if not text:
                self._send_rfc9457_error(422, "Invalid Text", "EMPTY_TEXT", "Text must not be empty.")
                return

            language = body.get("language", "vi").lower()
            if language not in ("vi", "vietnamese"):
                self._send_rfc9457_error(
                    422,
                    "Unsupported Language",
                    "UNSUPPORTED_LANGUAGE",
                    f"VieNeu-TTS only supports Vietnamese ('vi'), received '{language}'.",
                )
                return

            voice_id = body.get("voice_id", "hai_dang")
            params = body.get("parameters", {})
            ref_audio = params.get("ref_audio")

            # Extract native control parameters with safe defaults
            temperature = float(params.get("temperature", 0.8))
            top_p = float(params.get("top_p", 0.95))
            top_k = int(params.get("top_k", 25))
            repetition_penalty = float(params.get("repetition_penalty", 1.2))
            repetition_window = int(params.get("repetition_window", 50))
            speed = float(params.get("speed", body.get("speed", 1.0)))
            denoise = bool(params.get("denoise", True))

            try:
                model = model_manager.get_model()

                infer_kwargs = {
                    "text": text,
                    "temperature": max(0.1, min(1.5, temperature)),
                    "top_p": max(0.1, min(1.0, top_p)),
                    "top_k": max(1, min(100, top_k)),
                    "repetition_penalty": max(1.0, min(2.5, repetition_penalty)),
                    "repetition_window": max(10, min(200, repetition_window)),
                }

                # Zero-shot voice cloning mode vs Preset voice mode
                if ref_audio:
                    ref_path = Path(ref_audio).resolve()
                    if not ref_path.exists():
                        self._send_rfc9457_error(
                            404,
                            "Reference Audio Not Found",
                            "REF_AUDIO_MISSING",
                            f"Reference audio file does not exist: {ref_path}",
                        )
                        return

                    infer_kwargs["ref_audio"] = str(ref_path)
                    infer_kwargs["denoise"] = denoise
                else:
                    if voice_id and voice_id.lower() not in VOICE_MAP:
                        self._send_rfc9457_error(
                            422,
                            "Unsupported Voice",
                            "UNSUPPORTED_VOICE",
                            f"Voice '{voice_id}' is not supported by VieNeu-TTS.",
                        )
                        return
                    resolved_voice = VOICE_MAP.get(voice_id.lower() if voice_id else "hai_dang", "Hải Đăng")
                    infer_kwargs["voice"] = resolved_voice

                audio_array = model.infer(**infer_kwargs)

                # Optional speed adjustment after neural synthesis.
                if abs(speed - 1.0) > 0.02 and len(audio_array) > 0:
                    try:
                        if _time_stretch_ready.is_set():
                            import librosa

                            audio_array = librosa.effects.time_stretch(audio_array, rate=float(speed))
                        else:
                            # The first librosa/numba compile can take tens of
                            # seconds. Return promptly with a bounded resample,
                            # while compiling the pitch-preserving path for the
                            # next request in the background.
                            _start_time_stretch_warmup()
                            audio_array = _fast_speed_adjust(audio_array, speed)
                    except Exception:
                        pass

                # Audio Gain Staging & Headroom Limiting:
                # Protect against PCM_16 digital hard clipping without altering dynamic consistency of normal segments.
                if len(audio_array) > 0:
                    peak_amp = float(np.max(np.abs(audio_array)))
                    if peak_amp > 0.98:
                        audio_array = audio_array * (0.98 / peak_amp)

                # Export to 16-bit PCM WAV in memory
                buf = io.BytesIO()
                sf.write(buf, audio_array, 48000, format="WAV", subtype="PCM_16")
                wav_bytes = buf.getvalue()

                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav_bytes)))
                self.send_header("X-Sample-Rate", "48000")
                self.send_header("X-Audio-Format", "wav")
                self.end_headers()
                self.wfile.write(wav_bytes)

            except Exception as exc:
                self._send_rfc9457_error(
                    500,
                    "Synthesis Failed",
                    "SYNTHESIS_ERROR",
                    f"VieNeu inference failed: {exc}",
                    retryable=False,
                )

        elif self.path == "/unload":
            model_manager.unload()
            resp = json.dumps({"status": "unloaded"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        else:
            self._send_rfc9457_error(404, "Endpoint Not Found", "NOT_FOUND", f"Unknown endpoint {self.path}")


def main():
    parser = argparse.ArgumentParser(description="VieNeu-TTS Worker Process")
    parser.add_argument("--port", type=int, default=0, help="Port to bind to (0 for ephemeral)")
    parser.add_argument("--auth-token", type=str, required=True, help="Shared authentication token")
    parser.add_argument("--parent-pid", type=int, default=None, help="PID of supervisor parent process")
    args = parser.parse_args()

    VieNeuWorkerHandler.auth_token = args.auth_token

    # Preload model in background or on first request
    # To ensure immediate health check passes, initialize server first
    server = ThreadedHTTPServer(("127.0.0.1", args.port), VieNeuWorkerHandler)
    assigned_port = server.server_port

    # Announce port to supervisor stdout
    sys.stdout.write(f"PORT:{assigned_port}\n")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
