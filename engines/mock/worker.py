"""
AI Voice Studio — Mock Engine Worker
Implements the standardized Engine Adapter HTTP protocol on loopback.
Generates valid synthetic PCM WAV audio for contract and pipeline testing.
"""

import argparse
import io
import json
import math
import os
import struct
import sys
import time
import wave
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


def generate_synthetic_wav(text: str, voice_id: str = "mock_female", speed: float = 1.0, sample_rate: int = 44100) -> bytes:
    """
    Generates a valid 16-bit Mono PCM WAV file with pitch modulation based on text and voice.
    """
    # Calculate duration: ~0.08s per character, clamped between 1.0s and 6.0s
    base_duration = max(1.0, min(6.0, len(text) * 0.08))
    duration = base_duration / max(0.25, min(4.0, speed))
    
    total_samples = int(sample_rate * duration)
    
    # Base frequency: lower for male voice, higher for female
    base_freq = 220.0 if "male" in str(voice_id).lower() else 440.0
    
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit (2 bytes per sample)
        wav_file.setframerate(sample_rate)
        
        raw_samples = bytearray()
        for i in range(total_samples):
            t = float(i) / sample_rate
            
            # Subtle vibrato/modulation so it sounds like an audible tone rather than harsh DC
            mod_freq = base_freq + 20.0 * math.sin(2.0 * math.pi * 5.0 * t)
            
            # Smooth envelope attack (0.05s) and release (0.1s)
            envelope = 1.0
            if t < 0.05:
                envelope = t / 0.05
            elif t > (duration - 0.1):
                envelope = max(0.0, (duration - t) / 0.1)
                
            sample_val = int(32767.0 * 0.5 * envelope * math.sin(2.0 * math.pi * mod_freq * t))
            # Clamp to 16-bit signed integer range
            sample_val = max(-32768, min(32767, sample_val))
            raw_samples.extend(struct.pack("<h", sample_val))
            
        wav_file.writeframes(raw_samples)
        
    return buf.getvalue()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class MockWorkerHandler(BaseHTTPRequestHandler):
    auth_token: str = ""
    engine_id: str = "mock-tts"

    def log_message(self, format, *args):
        # Silence default stderr logging to keep console clean
        pass

    def _check_auth(self) -> bool:
        token = self.headers.get("X-Worker-Token")
        if not token or token != self.auth_token:
            self._send_rfc9457_error(
                status=401,
                title="Unauthorized Worker Access",
                code="UNAUTHORIZED",
                detail="Missing or invalid X-Worker-Token header."
            )
            return False
        return True

    def _send_rfc9457_error(self, status: int, title: str, code: str, detail: str):
        err_body = json.dumps({
            "type": f"https://ai-voice-studio.local/errors/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
            "instance": self.path
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
            body = json.dumps({
                "status": "healthy",
                "engine_id": self.engine_id,
                "state": "ready",
                "device": "cpu",
                "memory_mb": 32
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/info":
            body = json.dumps({
                "engine_id": self.engine_id,
                "name": "Mock Synthetic Engine",
                "version": "1.0.0",
                "capabilities": ["text_to_speech", "speaker_selection"],
                "supported_languages": ["vi", "zh", "en"],
                "preset_voices": [
                    {"id": "mock_vi_female_1", "name": "Mock Nữ Tiếng Việt (Tổng hợp)", "language": "vi", "gender": "female"},
                    {"id": "mock_vi_male_1", "name": "Mock Nam Tiếng Việt (Tổng hợp)", "language": "vi", "gender": "male"},
                    {"id": "mock_zh_female_1", "name": "Mock Nữ Tiếng Trung", "language": "zh", "gender": "female"},
                    {"id": "mock_zh_male_1", "name": "Mock Nam Tiếng Trung", "language": "zh", "gender": "male"}
                ]
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self._send_rfc9457_error(404, "Endpoint Not Found", "NOT_FOUND", f"Path {self.path} does not exist.")

    def do_POST(self):
        if not self._check_auth():
            return

        if self.path == "/synthesize":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_rfc9457_error(400, "Bad Request", "INVALID_INPUT_PARAMS", "Empty request body.")
                return

            try:
                data = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except Exception as e:
                self._send_rfc9457_error(400, "Invalid JSON", "INVALID_INPUT_PARAMS", str(e))
                return

            text = data.get("text", "").strip()
            if not text:
                self._send_rfc9457_error(400, "Empty Text", "INVALID_INPUT_PARAMS", "Text parameter cannot be empty.")
                return

            language = data.get("language", "vi")
            if language not in ["vi", "zh", "en"]:
                self._send_rfc9457_error(422, "Unsupported Language", "UNSUPPORTED_LANGUAGE", f"Language '{language}' not supported by mock engine.")
                return

            voice_id = data.get("voice_id") or "mock_vi_female_1"
            speed = float(data.get("speed") or 1.0)
            sample_rate = int(data.get("sample_rate") or 44100)

            # Simulate brief inference computation
            time.sleep(0.15)

            wav_bytes = generate_synthetic_wav(text=text, voice_id=voice_id, speed=speed, sample_rate=sample_rate)

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.end_headers()
            self.wfile.write(wav_bytes)

        elif self.path == "/unload":
            body = json.dumps({"status": "unloaded", "freed_mb": 0}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self._send_rfc9457_error(404, "Endpoint Not Found", "NOT_FOUND", f"Path {self.path} does not exist.")


def main():
    parser = argparse.ArgumentParser(description="Mock Engine Worker")
    parser.add_argument("--port", type=int, default=0, help="Loopback port (0 for OS assigned)")
    parser.add_argument("--auth-token", type=str, required=True, help="Worker authentication secret")
    parser.add_argument("--parent-pid", type=int, default=0, help="Parent process ID for watchdog")
    args = parser.parse_args()

    MockWorkerHandler.auth_token = args.auth_token

    server = ThreadedHTTPServer(("127.0.0.1", args.port), MockWorkerHandler)
    actual_port = server.server_port

    # Print the allocated port to stdout for the supervisor to capture
    print(f"PORT:{actual_port}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
