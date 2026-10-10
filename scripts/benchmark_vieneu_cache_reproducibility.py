"""
AI Voice Studio — Phase 6A-R3: VieNeu Cache Reproducibility & Performance Benchmark
Executes repeated Cold vs Warm runs, measures median latency & RTF, validates process restart cache limits,
and analyzes the difference between deterministic inference (MSE=0) and actual speaker similarity.

Runs in: D:\\AIVoiceStudioData\\benchmarks\\envs\\vieneu_env\\Scripts\\python.exe
"""

import gc
import json
from pathlib import Path
import statistics
import sys
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import soundfile as sf
from vieneu import Vieneu

REF_A = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")
OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\cache_benchmark_results")
REPORT_JSON = OUTPUT_DIR / "cache_reproducibility_report.json"

TEST_TEXT = "Chào mừng bạn đến với phòng thí nghiệm giọng nói chuyên sâu của AI Voice Studio."


def run_benchmark():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assert REF_A.exists(), f"Reference audio not found: {REF_A}"

    print("\n" + "=" * 78)
    print(" AI VOICE STUDIO — PHASE 6A-R3: VIENEU CACHE REPRODUCIBILITY & PERF BENCHMARK")
    print("=" * 78)

    print("\n[Bước 1] Khởi tạo Model Vieneu (CPU / ONNX Runtime FP32)...")
    t0 = time.perf_counter()
    model = Vieneu()
    init_time = time.perf_counter() - t0
    print(f"  ✓ Khởi tạo Model hoàn tất trong {init_time:.2f}s | Cache REF_CACHE_MAX: {model.REF_CACHE_MAX}")

    # -------------------------------------------------------------
    # 1. COLD CACHE: 5 REPEATED RUNS (Clear cache before each run)
    # -------------------------------------------------------------
    print("\n[Bước 2] Thực thi 5 lượt suy luận COLD CACHE (Xóa cache trước mỗi lần chạy)...")
    cold_latencies = []
    cold_durations = []
    cold_rtfs = []
    cold_audios = []

    for i in range(1, 6):
        # Explicitly clear cache to simulate Cold reference enrollment
        model._ref_cache.clear()
        assert len(model._ref_cache) == 0

        t_start = time.perf_counter()
        audio = model.infer(TEST_TEXT, ref_audio=str(REF_A), denoise=True, use_ref_codes=True)
        lat = time.perf_counter() - t_start
        dur = len(audio) / 48000.0
        rtf = lat / dur

        cold_latencies.append(lat)
        cold_durations.append(dur)
        cold_rtfs.append(rtf)
        cold_audios.append(audio)
        print(f"  * Cold Run #{i}: Latency = {lat:.3f}s | Audio Duration = {dur:.2f}s | RTF = {rtf:.3f} | Cache Entries = {len(model._ref_cache)}")

    median_cold_latency = statistics.median(cold_latencies)
    median_cold_rtf = statistics.median(cold_rtfs)
    print(f"\n  >> TỔNG KẾT COLD CACHE (5 lượt):")
    print(f"     - Median Latency: {median_cold_latency:.3f}s (Min: {min(cold_latencies):.3f}s, Max: {max(cold_latencies):.3f}s)")
    print(f"     - Median RTF:     {median_cold_rtf:.3f} (Min: {min(cold_rtfs):.3f}, Max: {max(cold_rtfs):.3f})")

    # -------------------------------------------------------------
    # 2. WARM CACHE: 5 REPEATED RUNS (Cache populated)
    # -------------------------------------------------------------
    print("\n[Bước 3] Thực thi 5 lượt suy luận WARM CACHE (Bộ nhớ đệm LRU được giữ nguyên)...")
    warm_latencies = []
    warm_durations = []
    warm_rtfs = []
    warm_audios = []

    for i in range(1, 6):
        assert len(model._ref_cache) > 0, "Cache should already be populated"
        t_start = time.perf_counter()
        audio = model.infer(TEST_TEXT, ref_audio=str(REF_A), denoise=True, use_ref_codes=True)
        lat = time.perf_counter() - t_start
        dur = len(audio) / 48000.0
        rtf = lat / dur

        warm_latencies.append(lat)
        warm_durations.append(dur)
        warm_rtfs.append(rtf)
        warm_audios.append(audio)
        print(f"  * Warm Run #{i}: Latency = {lat:.3f}s | Audio Duration = {dur:.2f}s | RTF = {rtf:.3f} | Cache Entries = {len(model._ref_cache)}")

    median_warm_latency = statistics.median(warm_latencies)
    median_warm_rtf = statistics.median(warm_rtfs)
    time_saved = median_cold_latency - median_warm_latency
    pct_saved = (time_saved / median_cold_latency) * 100

    print(f"\n  >> TỔNG KẾT WARM CACHE (5 lượt):")
    print(f"     - Median Latency: {median_warm_latency:.3f}s (Min: {min(warm_latencies):.3f}s, Max: {max(warm_latencies):.3f}s)")
    print(f"     - Median RTF:     {median_warm_rtf:.3f} (Min: {min(warm_rtfs):.3f}, Max: {max(warm_rtfs):.3f})")
    print(f"     - Tiết kiệm thời gian nhờ LRU Cache: {time_saved * 1000:.1f}ms ({pct_saved:.1f}%)")

    # -------------------------------------------------------------
    # 3. WORKER RESTART LIFECYCLE SIMULATION (Process Boundary)
    # -------------------------------------------------------------
    print("\n[Bước 4] Mô phỏng Khởi động lại Tiến trình Worker (Process Lifecycle Boundary)...")
    print("  * Giải phóng bộ nhớ RAM và hủy instance Model hiện tại...")
    del model
    gc.collect()

    print("  * Khởi tạo lại Model Vieneu mới (tương đương worker subprocess mới spawn)...")
    t0_new = time.perf_counter()
    new_model = Vieneu()
    new_init_time = time.perf_counter() - t0_new
    print(f"  ✓ Model mới đã khởi tạo ({new_init_time:.2f}s) | Cache size ban đầu: {len(new_model._ref_cache)}")
    assert len(new_model._ref_cache) == 0, "New instance must have empty cache!"

    # First call after restart -> Must revert to Cold
    t_post_cold_start = time.perf_counter()
    audio_post_cold = new_model.infer(TEST_TEXT, ref_audio=str(REF_A), denoise=True, use_ref_codes=True)
    t_post_cold = time.perf_counter() - t_post_cold_start
    dur_post_cold = len(audio_post_cold) / 48000.0
    rtf_post_cold = t_post_cold / dur_post_cold
    print(f"  * Lượt gọi #1 Sau Restart (Reverted to Cold): Latency = {t_post_cold:.3f}s | RTF = {rtf_post_cold:.3f}")

    # Second call after restart -> Must transition back to Warm
    t_post_warm_start = time.perf_counter()
    audio_post_warm = new_model.infer(TEST_TEXT, ref_audio=str(REF_A), denoise=True, use_ref_codes=True)
    t_post_warm = time.perf_counter() - t_post_warm_start
    dur_post_warm = len(audio_post_warm) / 48000.0
    rtf_post_warm = t_post_warm / dur_post_warm
    print(f"  * Lượt gọi #2 Sau Restart (Back to Warm):    Latency = {t_post_warm:.3f}s | RTF = {rtf_post_warm:.3f}")

    # -------------------------------------------------------------
    # 4. DETERMINISTIC INFERENCE (MSE) vs SPEAKER SIMILARITY
    # -------------------------------------------------------------
    print("\n[Bước 5] Phân tích Khoa học: MSE Dạng Sóng vs Tính Tương Đồng Giọng Nói (Speaker Similarity)...")

    # Calculate MSE between Warm Run 1 and Warm Run 2
    len_w1 = len(warm_audios[0])
    len_w2 = len(warm_audios[1])
    min_len = min(len_w1, len_w2)
    mse_warm = float(np.mean((warm_audios[0][:min_len] - warm_audios[1][:min_len]) ** 2))
    max_diff_warm = float(np.max(np.abs(warm_audios[0][:min_len] - warm_audios[1][:min_len])))

    print(f"  * Đối chiếu Dạng sóng giữa Warm Run #1 và Warm Run #2:")
    print(f"    - Độ dài: Run 1 = {len_w1} mẫu, Run 2 = {len_w2} mẫu (Chênh lệch: {abs(len_w1 - len_w2)} mẫu)")
    print(f"    - Mean Squared Error (MSE): {mse_warm:.8e}")
    print(f"    - Maximum Absolute Difference: {max_diff_warm:.8e}")

    # Scientific rigor discussion
    print("\n  >> KẾT LUẬN & PHÂN BIỆT RÕ RÀNG:")
    print("  1. TÍNH CHẤT XÁC ĐỊNH (Deterministic Inference):")
    print(f"     Khi sử dụng cùng prompt văn bản, cùng mẫu tham chiếu, cùng seed/parameters trên CPU,")
    print(f"     giá trị MSE={mse_warm:.2e} chứng minh quá trình suy luận (inference execution) có tính lặp lại (reproducibility) cao.")
    print("  2. TUYỆT ĐỐI KHÔNG ĐÁNH ĐỒNG MSE=0 VỚI ĐỘ TƯƠNG ĐỒNG GIỌNG NÓI (Speaker Similarity):")
    print("     - MSE giữa 2 lần chạy inference chỉ đo sự giống nhau giữa BẢN SUY LUẬN A và BẢN SUY LUẬN B của chính model.")
    print("     - Speaker Similarity (Độ trung thực giọng nói) là độ tương đồng giữa ÂM THANH SINH RA và GIỌNG THỰC CỦA NGƯỜI NÓI trong mẫu tham chiếu.")
    print("     - Phải đo lường bằng Cosine Similarity của Speaker Embedding (Resemblyzer / WavLM / ECAPA-TDNN),")
    print("       chứ không thể lấy việc model sinh ra 2 file giống hệt nhau (MSE=0) để tuyên bố 'đạt độ giống giọng 100%'.")

    # Save results to JSON
    report = {
        "engine_id": "vieneu-tts",
        "hardware": "CPU (ONNX Runtime FP32)",
        "reference_audio": str(REF_A),
        "test_text": TEST_TEXT,
        "cold_runs": [
            {"run": i + 1, "latency_s": round(cold_latencies[i], 3), "duration_s": round(cold_durations[i], 2), "rtf": round(cold_rtfs[i], 3)}
            for i in range(5)
        ],
        "warm_runs": [
            {"run": i + 1, "latency_s": round(warm_latencies[i], 3), "duration_s": round(warm_durations[i], 2), "rtf": round(warm_rtfs[i], 3)}
            for i in range(5)
        ],
        "metrics_summary": {
            "median_cold_latency_s": round(median_cold_latency, 3),
            "median_cold_rtf": round(median_cold_rtf, 3),
            "median_warm_latency_s": round(median_warm_latency, 3),
            "median_warm_rtf": round(median_warm_rtf, 3),
            "time_saved_ms": round(time_saved * 1000, 1),
            "time_saved_percent": round(pct_saved, 1),
        },
        "restart_lifecycle": {
            "post_restart_cold_latency_s": round(t_post_cold, 3),
            "post_restart_cold_rtf": round(rtf_post_cold, 3),
            "post_restart_warm_latency_s": round(t_post_warm, 3),
            "post_restart_warm_rtf": round(rtf_post_warm, 3),
            "cache_persisted_across_process": False,
            "cache_nature": "In-memory LRU volatile cache (process-scoped)",
        },
        "reproducibility_vs_similarity": {
            "warm_run1_vs_run2_mse": mse_warm,
            "max_abs_difference": max_diff_warm,
            "is_deterministic": mse_warm < 1e-4,
            "scientific_note": "MSE=0 demonstrates deterministic execution of greedy decoding, NOT speaker similarity to ground truth.",
        },
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  ✓ Báo cáo đối soát hiệu năng và cache đã được ghi vào: {REPORT_JSON}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    run_benchmark()
