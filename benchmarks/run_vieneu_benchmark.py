"""
VieNeu-TTS Benchmark Runner (CPU / ONNX Runtime)
Measures:
- Model initialization latency (cold start)
- Preset voice inference (short and medium Vietnamese texts)
- Voice cloning pipeline with official reference sample
- Real-Time Factor (RTF), latency, CPU utilization, peak RAM
- Actual output audio metadata (sample rate, bit depth, duration, integrity)
- Repeated run stability (memory drift / variance)
"""

import os
import sys
import time
import json
from pathlib import Path

# Force UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import psutil
import soundfile as sf
import numpy as np

# Set model cache directory outside repository
os.environ["HF_HOME"] = r"D:\AIVoiceStudioData\benchmarks\models\huggingface"

OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\audio\vieneu")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_JSON = Path(r"D:\AIVoiceStudioData\benchmarks\vieneu_results.json")

TEXT_SHORT = "Xin chào, chào mừng bạn đến với hệ thống AI Voice Studio trên máy tính."
TEXT_MEDIUM = (
    "Trí tuệ nhân tạo đang thay đổi sâu sắc cách con người làm việc và sáng tạo. "
    "Với công nghệ chuyển đổi văn bản thành giọng nói chạy trực tiếp trên máy tính cá nhân, "
    "chúng ta có thể bảo đảm tính riêng tư, tốc độ phản hồi nhanh chóng mà không cần kết nối internet."
)

REF_AUDIO = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")


def get_process_memory_mb():
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)


def get_system_memory_mb():
    mem = psutil.virtual_memory()
    return mem.used / (1024 * 1024), mem.percent


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
    print("VIENEU-TTS BENCHMARK RUNNER (CPU / ONNX RUNTIME)")
    print("=" * 70)

    initial_ram_mb = get_process_memory_mb()
    sys_ram_mb, sys_ram_pct = get_system_memory_mb()
    print(f"Khởi điểm Process RSS: {initial_ram_mb:.1f} MB | System RAM: {sys_ram_mb:.1f} MB ({sys_ram_pct:.1f}%)")

    # 1. Model Loading / Initialization
    print("\n[1/5] Khởi tạo mô hình VieNeu-TTS (ONNX Backend)...")
    t0_load = time.perf_counter()
    from vieneu import Vieneu
    vieneu = Vieneu()
    t_load = time.perf_counter() - t0_load
    post_load_ram_mb = get_process_memory_mb()
    print(f"-> Thời gian nạp mô hình: {t_load:.2f}s | RAM sau nạp: {post_load_ram_mb:.1f} MB (Tăng: {post_load_ram_mb - initial_ram_mb:.1f} MB)")

    # List voices
    preset_voices = vieneu.list_preset_voices()
    voice_names = [v[0] for v in preset_voices]
    print(f"-> Số lượng giọng dựng sẵn: {len(preset_voices)}")
    print(f"-> Các giọng mẫu: {voice_names[:6]}")

    results = {
        "model_name": "VieNeu-TTS v3 Turbo",
        "backend": "ONNX Runtime (CPU)",
        "precision": "FP32",
        "python_version": sys.version.split()[0],
        "model_load_seconds": round(t_load, 3),
        "initial_ram_mb": round(initial_ram_mb, 1),
        "post_load_ram_mb": round(post_load_ram_mb, 1),
        "tests": []
    }

    # 2. Preset Voice Short Text (Cold Start)
    print("\n[2/5] Kiểm thử văn bản ngắn (Cold Start) - Giọng 'Hải Đăng'...")
    psutil.cpu_percent(interval=None)
    ram_before = get_process_memory_mb()
    t0 = time.perf_counter()
    audio_cold = vieneu.infer(TEXT_SHORT, voice="Hải Đăng")
    t_cold = time.perf_counter() - t0
    cpu_cold = psutil.cpu_percent(interval=None)
    ram_after = get_process_memory_mb()

    out_file_cold = OUTPUT_DIR / "01_preset_short_cold.wav"
    vieneu.save(audio_cold, str(out_file_cold))
    meta_cold = benchmark_audio_file(out_file_cold)
    rtf_cold = t_cold / meta_cold["duration_seconds"] if meta_cold["duration_seconds"] > 0 else 0

    print(f"-> Thời gian sinh: {t_cold:.2f}s | Độ dài audio: {meta_cold['duration_seconds']:.2f}s | RTF: {rtf_cold:.3f}")
    print(f"-> Sample Rate: {meta_cold['sample_rate']} Hz | CPU: {cpu_cold:.1f}% | RAM Peak: {ram_after:.1f} MB")

    results["tests"].append({
        "id": "preset_short_cold",
        "label": "Preset Giọng Hải Đăng - Văn bản ngắn (Cold)",
        "text": TEXT_SHORT,
        "voice": "Hải Đăng",
        "generation_time_sec": round(t_cold, 3),
        "audio_duration_sec": meta_cold["duration_seconds"],
        "rtf": round(rtf_cold, 3),
        "sample_rate": meta_cold["sample_rate"],
        "cpu_percent": cpu_cold,
        "ram_mb": round(ram_after, 1),
        "file": str(out_file_cold.name),
        "integrity": meta_cold
    })

    # 3. Preset Voice Medium Text (Warm Run)
    print("\n[3/5] Kiểm thử văn bản trung bình (Warm Run) - Giọng 'Mai Anh'...")
    psutil.cpu_percent(interval=None)
    t0 = time.perf_counter()
    audio_med = vieneu.infer(TEXT_MEDIUM, voice="Mai Anh")
    t_med = time.perf_counter() - t0
    cpu_med = psutil.cpu_percent(interval=None)
    ram_med = get_process_memory_mb()

    out_file_med = OUTPUT_DIR / "02_preset_medium_warm.wav"
    vieneu.save(audio_med, str(out_file_med))
    meta_med = benchmark_audio_file(out_file_med)
    rtf_med = t_med / meta_med["duration_seconds"] if meta_med["duration_seconds"] > 0 else 0

    print(f"-> Thời gian sinh: {t_med:.2f}s | Độ dài audio: {meta_med['duration_seconds']:.2f}s | RTF: {rtf_med:.3f}")
    print(f"-> Sample Rate: {meta_med['sample_rate']} Hz | CPU: {cpu_med:.1f}% | RAM Peak: {ram_med:.1f} MB")

    results["tests"].append({
        "id": "preset_medium_warm",
        "label": "Preset Giọng Mai Anh - Văn bản trung bình (Warm)",
        "text": TEXT_MEDIUM,
        "voice": "Mai Anh",
        "generation_time_sec": round(t_med, 3),
        "audio_duration_sec": meta_med["duration_seconds"],
        "rtf": round(rtf_med, 3),
        "sample_rate": meta_med["sample_rate"],
        "cpu_percent": cpu_med,
        "ram_mb": round(ram_med, 1),
        "file": str(out_file_med.name),
        "integrity": meta_med
    })

    # 4. Voice Cloning Pipeline with Official Reference Sample
    print("\n[4/5] Kiểm thử đường ống Voice Cloning (Zero-shot) với audio mẫu chuẩn...")
    if REF_AUDIO.exists():
        psutil.cpu_percent(interval=None)
        t0 = time.perf_counter()
        audio_clone = vieneu.infer(
            text=TEXT_SHORT,
            ref_audio=str(REF_AUDIO),
            denoise=True,
        )
        t_clone = time.perf_counter() - t0
        cpu_clone = psutil.cpu_percent(interval=None)
        ram_clone = get_process_memory_mb()

        out_file_clone = OUTPUT_DIR / "03_cloned_voice_official_ref.wav"
        vieneu.save(audio_clone, str(out_file_clone))
        meta_clone = benchmark_audio_file(out_file_clone)
        rtf_clone = t_clone / meta_clone["duration_seconds"] if meta_clone["duration_seconds"] > 0 else 0

        print(f"-> Thời gian clone: {t_clone:.2f}s | Độ dài audio: {meta_clone['duration_seconds']:.2f}s | RTF: {rtf_clone:.3f}")
        print(f"-> Sample Rate: {meta_clone['sample_rate']} Hz | CPU: {cpu_clone:.1f}% | RAM Peak: {ram_clone:.1f} MB")

        results["tests"].append({
            "id": "voice_clone_pipeline",
            "label": "Zero-shot Voice Cloning (Official Reference Sample)",
            "text": TEXT_SHORT,
            "ref_audio": str(REF_AUDIO.name),
            "generation_time_sec": round(t_clone, 3),
            "audio_duration_sec": meta_clone["duration_seconds"],
            "rtf": round(rtf_clone, 3),
            "sample_rate": meta_clone["sample_rate"],
            "cpu_percent": cpu_clone,
            "ram_mb": round(ram_clone, 1),
            "file": str(out_file_clone.name),
            "integrity": meta_clone
        })
    else:
        print(f"-> Không tìm thấy reference audio tại: {REF_AUDIO}")

    # 5. Stability & Repeatability (5 repeated runs)
    print("\n[5/5] Kiểm tra độ ổn định & rò rỉ bộ nhớ qua 5 lần chạy liên tiếp...")
    repeated_rtfs = []
    repeated_times = []
    ram_drift = []
    for i in range(1, 6):
        t0 = time.perf_counter()
        a = vieneu.infer(TEXT_SHORT, voice="Hải Đăng")
        elapsed = time.perf_counter() - t0
        dur = len(a) / 48000.0  # nominal
        rtf = elapsed / dur
        curr_ram = get_process_memory_mb()
        repeated_rtfs.append(round(rtf, 3))
        repeated_times.append(round(elapsed, 3))
        ram_drift.append(round(curr_ram, 1))
        print(f"  Vòng {i}: Thời gian={elapsed:.2f}s, RTF={rtf:.3f}, RAM={curr_ram:.1f} MB")

    results["stability"] = {
        "runs": 5,
        "latencies_sec": repeated_times,
        "rtfs": repeated_rtfs,
        "mean_rtf": round(float(np.mean(repeated_rtfs)), 3),
        "std_rtf": round(float(np.std(repeated_rtfs)), 3),
        "ram_drift_mb": ram_drift,
        "max_ram_mb": round(max(ram_drift), 1)
    }

    REPORT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=> Kết quả đã được ghi vào {REPORT_JSON}")
    print("=" * 70)


if __name__ == "__main__":
    main()
