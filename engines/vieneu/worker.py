"""
AI Voice Studio — VieNeu-TTS v3 Turbo Worker Process
Runs isolated in Python 3.12 (vieneu_env) on CPU via ONNX Runtime.
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

    def get_model(self):
        with self._lock:
            if self._model is None:
                self._state = "loading"
                try:
                    from vieneu import Vieneu
                    self._model = Vieneu()
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


model_manager = VieNeuModelManager()


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
                "device": "cpu",
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

            try:
                model = model_manager.get_model()

                # Zero-shot voice cloning mode
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

                    denoise = params.get("denoise", True)
                    audio_array = model.infer(text=text, ref_audio=str(ref_path), denoise=denoise)
                else:
                    # Preset voice mode
                    resolved_voice = VOICE_MAP.get(voice_id.lower() if voice_id else "", "Hải Đăng")
                    audio_array = model.infer(text=text, voice=resolved_voice)

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
