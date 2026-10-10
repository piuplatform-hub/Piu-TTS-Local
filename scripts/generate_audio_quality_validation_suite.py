"""
Phase 6A-R2: Audio Quality Validation Suite Generator
Generates a comprehensive listening evaluation set with technical acoustic metrics:
- Preset voice
- Clone Ref A
- Clone Ref B
- Voice Profile Ref A after restart
- Long multi-sentence paragraph
- Mixed numbers, dates, proper names, and code-switched English
Measures: duration, sample_rate, latency, RTF, clipping, peak, RMS, dynamic range.
"""

import json
import math
from pathlib import Path
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

OUTPUT_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\quality_validation_suite")
REF_A = Path(r"D:\AIVoiceStudioData\benchmarks\sources\VieNeu-TTS\examples\audio_ref\example.wav")
REF_B = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\test_clone\reference_b_sample.wav")


def analyze_audio_metrics(audio: np.ndarray, sr: int, latency_sec: float) -> dict:
    dur = len(audio) / float(sr)
    rtf = latency_sec / dur if dur > 0 else 0.0
    peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
    rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) > 0 else 0.0
    clipping = bool(peak >= 0.999)
    dyn_range_db = round(20 * math.log10(peak / (rms + 1e-9)), 2) if peak > 0 and rms > 0 else 0.0

    return {
        "duration_sec": round(dur, 2),
        "sample_rate": sr,
        "latency_sec": round(latency_sec, 3),
        "rtf": round(rtf, 3),
        "peak_amplitude": round(peak, 4),
        "rms_energy": round(rms, 4),
        "clipping": clipping,
        "dynamic_range_db": dyn_range_db,
    }


def main():
    print("\n" + "=" * 78)
    print(" AI VOICE STUDIO — PHASE 6A-R2: AUDIO QUALITY VALIDATION SUITE")
    print("=" * 78)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assert REF_A.exists(), f"Ref A not found: {REF_A}"
    assert REF_B.exists(), f"Ref B not found: {REF_B}"

    model = Vieneu()
    print("  ✓ VieNeu-TTS Engine Online (48 kHz)\n")

    eval_tasks = [
        {
            "name": "01_preset_hai_dang_standard.wav",
            "text": "Xin chào, đây là bản thu giọng đọc chuẩn Hải Đăng được tạo từ cấu hình cài sẵn của hệ thống.",
            "kwargs": {"voice": "Hải Đăng"},
            "desc": "Voice preset chuẩn (Nam miền Bắc)",
        },
        {
            "name": "02_clone_ref_a_short.wav",
            "text": "Xin chào các bạn, đây là giọng đọc nhân bản trực tiếp từ tệp âm thanh mẫu tham chiếu A.",
            "kwargs": {"ref_audio": str(REF_A), "use_ref_codes": True, "denoise": True},
            "desc": "Clone Ref A (Nữ, câu ngắn chuẩn mực)",
        },
        {
            "name": "03_clone_ref_b_short.wav",
            "text": "Xin chào các bạn, đây là giọng đọc nhân bản trực tiếp từ tệp âm thanh mẫu tham chiếu B.",
            "kwargs": {"ref_audio": str(REF_B), "use_ref_codes": True, "denoise": True},
            "desc": "Clone Ref B (Nữ, ngữ điệu phỏng vấn)",
        },
        {
            "name": "04_profile_ref_a_after_restart.wav",
            "text": "Hồ sơ giọng mẫu A được tái sử dụng thành công sau khi khởi động lại ứng dụng mà không suy giảm dữ liệu.",
            "kwargs": {"ref_audio": str(REF_A), "use_ref_codes": True, "denoise": True, "temperature": 0.8},
            "desc": "Voice Profile Ref A (mô phỏng sau restart)",
        },
        {
            "name": "05_long_multi_sentence_ref_a.wav",
            "text": "Hà Nội bước vào những ngày đầu thu với tiết trời se lạnh và làn gió heo may thoang thoảng. Những hàng cây trên phố Phan Đình Phùng bắt đầu trút lá vàng, tạo nên khung cảnh lãng mạn quen thuộc của thủ đô. Người dân thong thả dạo bước bên bờ hồ Hoàn Kiếm, tận hưởng không khí trong lành trước khi bắt đầu một ngày làm việc bận rộn.",
            "kwargs": {"ref_audio": str(REF_A), "use_ref_codes": True, "crossfade_p": 0.15, "silence_p": 0.2},
            "desc": "Đoạn văn dài nhiều câu (Kiểm định tính mạch lạc và tự nhiên)",
        },
        {
            "name": "06_mixed_numbers_dates_english_ref_a.wav",
            "text": "Hôm nay ngày 10 tháng 10 năm 2026, kỹ sư Alex Nguyễn tại công ty AI Tech đã phát hành bản cập nhật Studio Pro v6.0 với 12 tính năng mới và tốc độ xử lý nhanh hơn 45%.",
            "kwargs": {"ref_audio": str(REF_A), "use_ref_codes": True, "temperature": 0.75},
            "desc": "Đoạn văn chứa số, ngày tháng, tên riêng và từ tiếng Anh xen kẽ",
        },
    ]

    report_data = []

    for task in eval_tasks:
        print(f"  * Đang tổng hợp: {task['name']} ({task['desc']})...")
        t_start = time.perf_counter()
        audio = model.infer(task["text"], **task["kwargs"])
        latency = time.perf_counter() - t_start

        raw_peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0

        # Audio Gain Staging & Headroom Limiting (Consistent with Worker layer)
        # Only scales signals exceeding safe 0.98 ceiling to prevent digital PCM_16 clipping
        if len(audio) > 0 and raw_peak > 0.98:
            audio = audio * (0.98 / raw_peak)

        out_path = OUTPUT_DIR / task["name"]
        sf.write(str(out_path), audio, 48000, format="WAV", subtype="PCM_16")

        metrics = analyze_audio_metrics(audio, 48000, latency)
        metrics["raw_model_peak"] = round(raw_peak, 4)
        metrics["filename"] = task["name"]
        metrics["description"] = task["desc"]
        report_data.append(metrics)

        print(f"    -> Thời lượng: {metrics['duration_sec']}s | Latency: {metrics['latency_sec']}s | RTF: {metrics['rtf']} | Peak: {metrics['peak_amplitude']} | Clipping: {metrics['clipping']}")

    # Save summary report JSON
    with open(OUTPUT_DIR / "quality_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print(" BẢNG THÔNG SỐ KỸ THUẬT ÂM HỌC THỰC NGHIỆM")
    print("=" * 78)
    print(f"{'Tệp Âm Thanh':<35} | {'Thời lượng':<10} | {'Latency':<8} | {'RTF':<6} | {'Peak':<7} | {'RMS':<7} | {'Clipping':<8}")
    print("-" * 90)
    for m in report_data:
        print(f"{m['filename']:<35} | {str(m['duration_sec'])+'s':<10} | {str(m['latency_sec'])+'s':<8} | {m['rtf']:<6} | {m['peak_amplitude']:<7} | {m['rms_energy']:<7} | {str(m['clipping']):<8}")
    print("=" * 90)
    print(f"\n  ✓ Đã lưu toàn bộ bộ nghe thử tại: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
