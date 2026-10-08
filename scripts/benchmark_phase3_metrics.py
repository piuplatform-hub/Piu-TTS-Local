"""
AI Voice Studio — Phase 3 Neural Engine Hardware Benchmark & Runtime Metrics
Measures real performance on target Windows 11 host:
- CPU: Intel Core i5-12400F (6P/12T)
- GPU: NVIDIA GeForce RTX 3050 (6GB VRAM)
- RAM: 16GB Host DDR4

Engines evaluated:
1. VieNeu-TTS v3 Turbo (ONNX Runtime FP32 CPU)
2. Qwen3-TTS 0.6B CustomVoice (PyTorch bfloat16 CUDA)
"""

import asyncio
import io
import json
import os
from pathlib import Path
import sys
import time
import wave

# Ensure root package on path
workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root))

from apps.server.src.supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest
from engine_sdk.protocol import SynthesisRequest


BENCHMARK_PROMPTS = {
    "vi_short": "Xin chào, đây là kiểm thử tốc độ.",
    "vi_medium": "Chào mừng bạn đến với AI Voice Studio. Đây là nền tảng xử lý và tổng hợp giọng nói AI chuyên nghiệp chạy hoàn toàn cục bộ trên máy tính của bạn.",
    "vi_long": "Hôm nay thời tiết tại thủ đô Hà Nội và các tỉnh phía Bắc duy trì trạng thái nhiều mây, độ ẩm cao và có sương mù nhẹ vào sáng sớm. Đến trưa chiều mây giảm dần, trời hửng nắng nhẹ, nhiệt độ cao nhất phổ biến từ hai mươi lăm đến hai mươi bảy độ C.",
    "zh_short": "你好，语音合成测试。",
    "zh_medium": "你好，欢迎使用 AI Voice Studio 本地多模型语音合成系统。",
    "zh_long": "人工智能正在快速重塑现代技术与数字内容创作方式。本地化部署的大语言模型与语音合成系统为创作者提供了更高的数据安全与隐私保护。",
}


def analyze_wav(audio_bytes: bytes):
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.getnframes()
        channels = wf.getnchannels()
        duration = frames / float(sr)
        return sr, channels, duration


async def benchmark_engine(manifest_path: Path, engine_id: str, prompt_keys: list, language: str, voice_id: str):
    print(f"\n=======================================================")
    print(f" BENCHMARKING ENGINE: {engine_id}")
    print(f"=======================================================")

    manifest = EngineManifest.from_file(str(manifest_path))

    # Measure cold worker startup
    t0_start = time.perf_counter()
    worker = await supervisor.start_worker(manifest, workspace_root)
    t_worker_up = time.perf_counter() - t0_start
    print(f"-> Worker process spawned and ready in {t_worker_up:.2f}s (PID: {worker.process.pid})")

    results = []

    for i, key in enumerate(prompt_keys):
        text = BENCHMARK_PROMPTS[key]
        print(f"\n--- Run {i+1}: {key} ({len(text)} chars) ---")

        req = SynthesisRequest(
            job_id=f"bench-{engine_id}-{key}",
            text=text,
            language=language,
            voice_id=voice_id,
        )

        t0_infer = time.perf_counter()
        audio_bytes = await worker.client.synthesize(req)
        wall_time = time.perf_counter() - t0_infer

        sr, channels, duration = analyze_wav(audio_bytes)
        rtf = wall_time / duration if duration > 0 else 0.0

        # Query worker health telemetry
        health = await worker.client.get_health()

        entry = {
            "prompt_key": key,
            "char_count": len(text),
            "wall_time_sec": round(wall_time, 3),
            "audio_duration_sec": round(duration, 3),
            "sample_rate_hz": sr,
            "channels": channels,
            "audio_size_bytes": len(audio_bytes),
            "rtf": round(rtf, 3),
            "worker_rss_mb": getattr(health, "memory_mb", 0),
            "worker_vram_mb": getattr(health, "vram_mb", 0),
        }
        results.append(entry)

        print(f"   Audio Duration: {duration:.2f}s | Wall Time: {wall_time:.2f}s | RTF: {rtf:.2f}")
        print(f"   Sample Rate: {sr}Hz | Worker RSS: {getattr(health, 'memory_mb', 0)}MB | VRAM: {getattr(health, 'vram_mb', 0)}MB")

    return {
        "engine_id": engine_id,
        "worker_startup_sec": round(t_worker_up, 2),
        "runs": results,
    }


async def main():
    report = {}

    try:
        # 1. Benchmark VieNeu-TTS (CPU)
        vieneu_manifest = workspace_root / "engines" / "vieneu" / "engine.manifest.json"
        vieneu_data = await benchmark_engine(
            manifest_path=vieneu_manifest,
            engine_id="vieneu-tts",
            prompt_keys=["vi_short", "vi_medium", "vi_long"],
            language="vi",
            voice_id="hai_dang",
        )
        report["vieneu_tts"] = vieneu_data

        # 2. Benchmark Qwen3-TTS (GPU)
        qwen3_manifest = workspace_root / "engines" / "qwen3" / "engine.manifest.json"
        qwen3_data = await benchmark_engine(
            manifest_path=qwen3_manifest,
            engine_id="qwen3-tts",
            prompt_keys=["zh_short", "zh_medium", "zh_long"],
            language="zh",
            voice_id="vivian",
        )
        report["qwen3_tts"] = qwen3_data

    finally:
        supervisor.shutdown_all()

    # Save benchmark json
    out_dir = workspace_root / "docs" / "reports" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase3_runtime_benchmark_raw.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nRaw metrics saved to: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
