"""
AI Voice Studio — Qwen3-TTS 0.6B CustomVoice Worker Process
Runs isolated in Python 3.12 (qwen3_env) on NVIDIA GPU via PyTorch CUDA.
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
import torch

ENGINE_ID = "qwen3-tts"
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

SUPPORTED_SPEAKERS = [
    {"id": "vivian", "name": "Vivian (Young Female)", "gender": "female"},
    {"id": "uncle_fu", "name": "Uncle Fu (Mature Male)", "gender": "male"},
    {"id": "serena", "name": "Serena (Gentle Female)", "gender": "female"},
    {"id": "aiden", "name": "Aiden (Young Male)", "gender": "male"},
    {"id": "dylan", "name": "Dylan (Warm Male)", "gender": "male"},
    {"id": "eric", "name": "Eric (Standard Male)", "gender": "male"},
    {"id": "ono_anna", "name": "Ono Anna (Bright Female)", "gender": "female"},
    {"id": "ryan", "name": "Ryan (Dynamic Male)", "gender": "male"},
    {"id": "sohee", "name": "Sohee (Soft Female)", "gender": "female"},
]

SPEAKER_IDS = {s["id"] for s in SUPPORTED_SPEAKERS}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Qwen3ModelManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._state = "unloaded"

    def get_model(self):
        with self._lock:
            if self._model is None:
                self._state = "loading"
                if not torch.cuda.is_available():
                    self._state = "error"
                    raise RuntimeError("CUDA is not available on this host. Qwen3-TTS requires an NVIDIA GPU.")

                free_bytes, total_bytes = torch.cuda.mem_get_info()
                free_mb = free_bytes / (1024 * 1024)
                if free_mb < 2000:
                    self._state = "error"
                    raise RuntimeError(f"Insufficient GPU VRAM. Required: 2000MB, Available: {free_mb:.0f}MB.")

                try:
                    from qwen_tts import Qwen3TTSModel
                    self._model = Qwen3TTSModel.from_pretrained(
                        MODEL_ID,
                        device_map="cuda:0",
                        dtype=torch.bfloat16,
                    )
                    self._state = "ready"
                except Exception as exc:
                    self._state = "error"
                    raise RuntimeError(f"Failed to load Qwen3-TTS model: {exc}")

            return self._model

    def unload(self):
        with self._lock:
            if self._model is not None:
                self._state = "unloading"
                del self._model
                self._model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            self._state = "unloaded"

    @property
    def state(self) -> str:
        return self._state


model_manager = Qwen3ModelManager()


class Qwen3WorkerHandler(BaseHTTPRequestHandler):
    auth_token: str = ""

    def log_message(self, format, *args):
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
            vram_alloc_mb = int(torch.cuda.memory_allocated() / (1024 * 1024)) if torch.cuda.is_available() else 0
            resp = json.dumps({
                "status": "healthy",
                "engine_id": ENGINE_ID,
                "state": model_manager.state if model_manager.state != "unloaded" else "ready",
                "device": "gpu",
                "memory_mb": rss_mb,
                "vram_mb": vram_alloc_mb,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        elif self.path == "/info":
            voices = [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "language": "zh",
                    "gender": s["gender"],
                    "description": f"Mandarin Chinese ({s['gender']})",
                }
                for s in SUPPORTED_SPEAKERS
            ]
            resp = json.dumps({
                "engine_id": ENGINE_ID,
                "name": "Qwen3-TTS 0.6B CustomVoice",
                "version": "1.0.0",
                "capabilities": ["text_to_speech", "speaker_selection"],
                "supported_languages": ["zh"],
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

            language = body.get("language", "zh").lower()
            if language not in ("zh", "chinese"):
                self._send_rfc9457_error(
                    422,
                    "Unsupported Language",
                    "UNSUPPORTED_LANGUAGE",
                    f"Qwen3-TTS only supports Mandarin Chinese ('zh'), received '{language}'.",
                )
                return

            # Check voice/speaker
            voice_id = body.get("voice_id", "vivian").lower()
            params = body.get("parameters", {})
            speaker_param = params.get("speaker", voice_id).lower()

            if speaker_param not in SPEAKER_IDS:
                # Default to vivian if unknown
                speaker_param = "vivian"

            # Capitalize as expected by model (e.g. Vivian, Uncle_Fu, Serena)
            capitalized_speaker = speaker_param.capitalize()
            if speaker_param == "uncle_fu":
                capitalized_speaker = "Uncle_Fu"
            elif speaker_param == "ono_anna":
                capitalized_speaker = "Ono_Anna"

            try:
                model = model_manager.get_model()

                # Generate speech on GPU
                torch.cuda.reset_peak_memory_stats()
                wavs, sample_rate = model.generate_custom_voice(
                    text=text,
                    language="Chinese",
                    speaker=capitalized_speaker,
                )

                # wavs is list of numpy arrays or torch tensors
                audio_array = wavs[0]
                if hasattr(audio_array, "cpu"):
                    audio_array = audio_array.cpu().numpy()

                # Ensure 1D float numpy array
                if audio_array.ndim > 1:
                    audio_array = audio_array.squeeze()

                buf = io.BytesIO()
                sf.write(buf, audio_array, int(sample_rate), format="WAV", subtype="PCM_16")
                wav_bytes = buf.getvalue()

                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav_bytes)))
                self.send_header("X-Sample-Rate", str(sample_rate))
                self.send_header("X-Audio-Format", "wav")
                self.end_headers()
                self.wfile.write(wav_bytes)

            except torch.cuda.OutOfMemoryError as oom:
                torch.cuda.empty_cache()
                self._send_rfc9457_error(
                    503,
                    "GPU Out of Memory",
                    "CUDA_OOM",
                    f"CUDA Out of Memory during Qwen3 synthesis: {oom}",
                    retryable=False,
                )
            except Exception as exc:
                self._send_rfc9457_error(
                    500,
                    "Synthesis Failed",
                    "SYNTHESIS_ERROR",
                    f"Qwen3-TTS inference failed: {exc}",
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
    parser = argparse.ArgumentParser(description="Qwen3-TTS Worker Process")
    parser.add_argument("--port", type=int, default=0, help="Port to bind to (0 for ephemeral)")
    parser.add_argument("--auth-token", type=str, required=True, help="Shared authentication token")
    parser.add_argument("--parent-pid", type=int, default=None, help="PID of supervisor parent process")
    args = parser.parse_args()

    Qwen3WorkerHandler.auth_token = args.auth_token

    server = ThreadedHTTPServer(("127.0.0.1", args.port), Qwen3WorkerHandler)
    assigned_port = server.server_port

    sys.stdout.write(f"PORT:{assigned_port}\n")
    sys.stdout.flush()

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
