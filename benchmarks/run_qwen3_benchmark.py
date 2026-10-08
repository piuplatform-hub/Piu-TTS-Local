"""
Qwen3-TTS 0.6B CustomVoice Benchmark Runner (PyTorch CUDA on RTX 3050 6GB)
Measures:
- Pre-inference GPU VRAM safety check
- Cold start model load latency & baseline VRAM footprint
- Numeric precision: torch.float16 / torch.bfloat16
- Synthesis latency, audio duration, Real-Time Factor (RTF) across Short, Medium, Long Mandarin Chinese texts
- Preset speakers: Vivian, Uncle_Fu, Serena
- Peak VRAM allocated / reserved during synthesis
- Audio output metadata and integrity (sample rate, channels, amplitude, clipping)
- Error recovery test & repeated run stability
"""

import os
import sys
import time
import json
from pathlib import Path

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configure model weights path outside application source
os.environ["HF_HOME"] = r"D:\AIVoiceStudioData\benchmarks\models\huggingface"

import torch
import psutil
import soundfile as sf
import numpy as np

OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\audio\qwen3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_JSON = Path(r"D:\AIVoiceStudioData\benchmarks\qwen3_results.json")

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"

TEXT_SHORT = "你好，欢迎使用本地AI语音合成工作台。"
TEXT_MEDIUM = (
    "人工智能正在深刻改变内容创作与人机交互的方式。"
    "通过本地化语音大模型，用户可以在保护隐私的前提下获得高质量且自然的语音体验。"
)
TEXT_LONG = (
    "中国拥有悠久的历史和灿烂的文化，从长城脚下的古老传说到现代繁华都市的高铁网络，"
    "传统与现代在这里交相辉映。语言与文字作为文明的载体，记录了数千年的智慧与创造力，"
    "而在人工智能时代，声音的数字化再现赋予了语言新的生命。"
)


def get_vram_info_mb():
    if not torch.cuda.is_available():
        return 0, 0, 0
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    allocated_bytes = torch.cuda.memory_allocated()
    reserved_bytes = torch.cuda.memory_reserved()
    return (
        allocated_bytes / (1024 * 1024),
        reserved_bytes / (1024 * 1024),
        free_bytes / (1024 * 1024),
        total_bytes / (1024 * 1024),
    )


def benchmark_audio_file(file_path: Path):
    data, sr = sf.read(str(file_path))
    duration = len(data) / sr
    max_amp = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
    is_clipping = max_amp >= 0.999
    is_silent = max_amp < 0.001
    return {
        "sample_rate": int(sr),
        "duration_seconds": round(duration, 3),
        "channels": 1 if data.ndim == 1 else data.shape[1],
        "samples_count": len(data),
        "max_amplitude": round(max_amp, 4),
        "is_clipping": is_clipping,
        "is_silent": is_silent,
    }


def main():
    print("=" * 70)
    print("QWEN3-TTS 0.6B CUSTOMVOICE BENCHMARK RUNNER (PYTORCH CUDA)")
    print("=" * 70)

    # 1. Hardware Safety & Pre-flight VRAM Inspection
    assert torch.cuda.is_available(), "CUDA is not available on this machine!"
    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    alloc_mb, res_mb, free_mb, total_mb = get_vram_info_mb()

    print(f"GPU: {device_name} (Capability: sm_{capability[0]}{capability[1]})")
    print(f"Total VRAM: {total_mb:.1f} MB | Free VRAM: {free_mb:.1f} MB | Allocated: {alloc_mb:.1f} MB")

    if free_mb < 2000:
        raise RuntimeError(f"VRAM không đủ an toàn để chạy mô hình! Cần tối thiểu 2000 MB, hiện có {free_mb:.1f} MB")

    # Determine precision: RTX 3050 (sm_86) supports bfloat16 and float16
    dtype = torch.bfloat16
    print(f"Numeric Precision Lựa chọn: {dtype}")

    # 2. Model Loading (Cold Start)
    print(f"\n[1/6] Nạp mô hình {MODEL_ID}...")
    torch.cuda.reset_peak_memory_stats()
    t0_load = time.perf_counter()

    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        device_map="cuda:0",
        dtype=dtype,
    )
    t_load = time.perf_counter() - t0_load

    alloc_post_load, res_post_load, free_post_load, _ = get_vram_info_mb()
    print(f"-> Thời gian nạp: {t_load:.2f}s")
    print(f"-> VRAM sau khi nạp: Allocated={alloc_post_load:.1f} MB, Reserved={res_post_load:.1f} MB, Free={free_post_load:.1f} MB")

    supported_speakers = getattr(model, "get_supported_speakers", lambda: [])()
    print(f"-> Danh sách giọng hỗ trợ: {supported_speakers}")

    results = {
        "model_id": MODEL_ID,
        "device": device_name,
        "dtype": str(dtype),
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
        "model_load_time_sec": round(t_load, 3),
        "baseline_vram_allocated_mb": round(alloc_post_load, 1),
        "baseline_vram_reserved_mb": round(res_post_load, 1),
        "supported_speakers": supported_speakers,
        "tests": []
    }

    # 3. Test 1: Short Mandarin Text (Cold Run) - Speaker: Vivian
    print("\n[2/6] Kiểm thử câu ngắn tiếng Trung (Cold Run) - Giọng 'Vivian'...")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    wavs_short, sr_short = model.generate_custom_voice(
        text=TEXT_SHORT,
        language="Chinese",
        speaker="Vivian",
    )
    t_short = time.perf_counter() - t0
    peak_vram_short = torch.cuda.max_memory_allocated() / (1024 * 1024)

    out_file_short = OUTPUT_DIR / "01_short_chinese_vivian.wav"
    sf.write(str(out_file_short), wavs_short[0], sr_short)
    meta_short = benchmark_audio_file(out_file_short)
    rtf_short = t_short / meta_short["duration_seconds"] if meta_short["duration_seconds"] > 0 else 0

    print(f"-> Thời gian sinh: {t_short:.2f}s | Độ dài audio: {meta_short['duration_seconds']:.2f}s | RTF: {rtf_short:.3f}")
    print(f"-> Peak VRAM: {peak_vram_short:.1f} MB | Sample Rate: {meta_short['sample_rate']} Hz")

    results["tests"].append({
        "id": "short_chinese_vivian",
        "label": "Câu ngắn tiếng Trung - Giọng Vivian (Cold)",
        "text": TEXT_SHORT,
        "speaker": "Vivian",
        "generation_time_sec": round(t_short, 3),
        "audio_duration_sec": meta_short["duration_seconds"],
        "rtf": round(rtf_short, 3),
        "peak_vram_mb": round(peak_vram_short, 1),
        "file": str(out_file_short.name),
        "integrity": meta_short,
    })

    # 4. Test 2: Medium Mandarin Text (Warm Run) - Speaker: Uncle_Fu
    print("\n[3/6] Kiểm thử đoạn văn trung bình tiếng Trung (Warm Run) - Giọng 'Uncle_Fu'...")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    wavs_med, sr_med = model.generate_custom_voice(
        text=TEXT_MEDIUM,
        language="Chinese",
        speaker="Uncle_Fu",
    )
    t_med = time.perf_counter() - t0
    peak_vram_med = torch.cuda.max_memory_allocated() / (1024 * 1024)

    out_file_med = OUTPUT_DIR / "02_medium_chinese_uncle_fu.wav"
    sf.write(str(out_file_med), wavs_med[0], sr_med)
    meta_med = benchmark_audio_file(out_file_med)
    rtf_med = t_med / meta_med["duration_seconds"] if meta_med["duration_seconds"] > 0 else 0

    print(f"-> Thời gian sinh: {t_med:.2f}s | Độ dài audio: {meta_med['duration_seconds']:.2f}s | RTF: {rtf_med:.3f}")
    print(f"-> Peak VRAM: {peak_vram_med:.1f} MB | Sample Rate: {meta_med['sample_rate']} Hz")

    results["tests"].append({
        "id": "medium_chinese_uncle_fu",
        "label": "Đoạn vừa tiếng Trung - Giọng Uncle_Fu (Warm)",
        "text": TEXT_MEDIUM,
        "speaker": "Uncle_Fu",
        "generation_time_sec": round(t_med, 3),
        "audio_duration_sec": meta_med["duration_seconds"],
        "rtf": round(rtf_med, 3),
        "peak_vram_mb": round(peak_vram_med, 1),
        "file": str(out_file_med.name),
        "integrity": meta_med,
    })

    # 5. Test 3: Long Mandarin Passage (Warm Run) - Speaker: Serena
    print("\n[4/6] Kiểm thử đoạn văn dài tiếng Trung - Giọng 'Serena'...")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    wavs_long, sr_long = model.generate_custom_voice(
        text=TEXT_LONG,
        language="Chinese",
        speaker="Serena",
    )
    t_long = time.perf_counter() - t0
    peak_vram_long = torch.cuda.max_memory_allocated() / (1024 * 1024)

    out_file_long = OUTPUT_DIR / "03_long_chinese_serena.wav"
    sf.write(str(out_file_long), wavs_long[0], sr_long)
    meta_long = benchmark_audio_file(out_file_long)
    rtf_long = t_long / meta_long["duration_seconds"] if meta_long["duration_seconds"] > 0 else 0

    print(f"-> Thời gian sinh: {t_long:.2f}s | Độ dài audio: {meta_long['duration_seconds']:.2f}s | RTF: {rtf_long:.3f}")
    print(f"-> Peak VRAM: {peak_vram_long:.1f} MB | Sample Rate: {meta_long['sample_rate']} Hz")

    results["tests"].append({
        "id": "long_chinese_serena",
        "label": "Đoạn dài tiếng Trung - Giọng Serena (Warm)",
        "text": TEXT_LONG,
        "speaker": "Serena",
        "generation_time_sec": round(t_long, 3),
        "audio_duration_sec": meta_long["duration_seconds"],
        "rtf": round(rtf_long, 3),
        "peak_vram_mb": round(peak_vram_long, 1),
        "file": str(out_file_long.name),
        "integrity": meta_long,
    })

    # 6. Error Recovery Verification
    print("\n[5/6] Kiểm tra khả năng tự khôi phục sau lỗi (Error Recovery)...")
    error_caught = False
    try:
        model.generate_custom_voice(
            text="Kiểm tra bắt lỗi",
            speaker="NonExistentSpeaker_12345",
        )
    except Exception as e:
        error_caught = True
        print(f"-> Bắt được lỗi mong đợi: {type(e).__name__}: {str(e)[:80]}...")

    # Immediately attempt valid generation after error
    t0_rec = time.perf_counter()
    wavs_rec, sr_rec = model.generate_custom_voice(
        text="恢复正常。",
        language="Chinese",
        speaker="Vivian",
    )
    t_rec = time.perf_counter() - t0_rec
    recovery_successful = len(wavs_rec) > 0 and len(wavs_rec[0]) > 0
    print(f"-> Khôi phục suy luận bình thường sau lỗi: {recovery_successful} (Thời gian={t_rec:.2f}s)")

    results["error_recovery"] = {
        "error_caught_as_expected": error_caught,
        "recovery_successful": recovery_successful,
        "post_error_latency_sec": round(t_rec, 3),
    }

    # 7. Repeated Runs Stability (3 runs on short text)
    print("\n[6/6] Kiểm tra tính ổn định qua các lần chạy liên tiếp...")
    repeated_rtfs = []
    repeated_times = []
    for i in range(1, 4):
        t0_rep = time.perf_counter()
        w, _ = model.generate_custom_voice(
            text=TEXT_SHORT,
            language="Chinese",
            speaker="Vivian",
        )
        t_rep = time.perf_counter() - t0_rep
        dur = len(w[0]) / sr_short
        rtf = t_rep / dur
        repeated_rtfs.append(round(rtf, 3))
        repeated_times.append(round(t_rep, 3))
        print(f"  Vòng {i}: Thời gian={t_rep:.2f}s, RTF={rtf:.3f}")

    results["stability"] = {
        "runs": 3,
        "latencies_sec": repeated_times,
        "rtfs": repeated_rtfs,
        "mean_rtf": round(float(np.mean(repeated_rtfs)), 3),
        "std_rtf": round(float(np.std(repeated_rtfs)), 3),
    }

    # Final memory release
    torch.cuda.empty_cache()
    final_alloc_mb, final_res_mb, final_free_mb, _ = get_vram_info_mb()
    results["final_gpu_state"] = {
        "vram_allocated_mb": round(final_alloc_mb, 1),
        "vram_reserved_mb": round(final_res_mb, 1),
        "vram_free_mb": round(final_free_mb, 1),
    }

    REPORT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=> Kết quả Qwen3-TTS đã được lưu vào {REPORT_JSON}")
    print("=" * 70)


if __name__ == "__main__":
    main()
