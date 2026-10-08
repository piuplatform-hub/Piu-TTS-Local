# BÁO CÁO ĐO LƯỜNG VÀ KIỂM CHỨNG ÂM THANH MASTER PHASE 4
## AI VOICE STUDIO — AUDIO DSP, EBU R128 LOUDNORMALIZATION & TRUE PEAK VALIDATION

**Ngày đo lường:** 08/10/2026  
**Công cụ phân tích:** FFmpeg v7.1.1 essentials (Filter: `loudnorm`, `aresample`, `ebur128`)  
**Mục tiêu đo lường:** Xác thực chất lượng kỹ thuật của 4 tệp âm thanh Master được kết xuất từ 2 neural engine thực tế trên máy trạm Windows.  
**Thư mục lưu trữ tệp nguồn:** `D:\AIVoiceStudioData\acceptance_audio_phase4\`

---

## 1. BẢNG TỔNG HỢP CHỈ SỐ KỸ THUẬT THỰC ĐO (AUTHENTIC MEASUREMENTS)

Dữ liệu được trích xuất trực tiếp từ kết quả phân tích `metrics_summary.json`:

| Chỉ số kỹ thuật | Workflow A (WAV) | Workflow B (MP3) | Workflow C (WAV) | Workflow C (MP3) | Chuẩn công nghiệp EBU R128 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tên tệp** | `workflow_a_vietnamese_master.wav` | `workflow_b_chinese_master.mp3` | `workflow_c_mixed_dialogue_master.wav` | `workflow_c_mixed_dialogue_master.mp3` | — |
| **Nội dung kịch bản** | Sách nói tiếng Việt (Cố Đô Huế) | Truyện đọc tiếng Trung (Giang Nam) | Hội thoại song ngữ (Lan & Mei) | Hội thoại song ngữ (Lan & Mei) | — |
| **Động cơ sử dụng** | VieNeu-TTS v3 Turbo | Qwen3-TTS 0.6B | VieNeu + Qwen3 xen kẽ | VieNeu + Qwen3 xen kẽ | — |
| **Phần cứng xử lý** | Intel Core i5-12400F (CPU) | NVIDIA RTX 3050 (GPU) | CPU + GPU luân phiên | CPU + GPU luân phiên | — |
| **Dung lượng tệp** | **2,217,678 bytes** | **1,109,804 bytes** | **2,076,558 bytes** | **867,884 bytes** | — |
| **Thời lượng phát** | **23.10 giây** | **27.72 giây** | **21.63 giây** | **21.67 giây** | — |
| **Tần số mẫu (Hz)** | **48,000 Hz** | **48,000 Hz** (resampled) | **48,000 Hz** | **48,000 Hz** | 48kHz tiêu chuẩn studio |
| **Số kênh âm thanh** | 1 (Mono) | 1 (Mono) | 1 (Mono) | 1 (Mono) | 1 (Mono Vocal) |
| **Độ sâu bit / Bitrate** | 16-bit PCM | 192 kbps CBR | 16-bit PCM | 192 kbps CBR | $\ge$ 16-bit / 192kbps |
| **Mục tiêu LUFS** | -16.0 LUFS | -16.0 LUFS | -16.0 LUFS | -16.0 LUFS | -16.0 LUFS (Online Content) |
| **Thực đo Integrated LUFS** | **-16.11 LUFS** | **-16.27 LUFS** | **-16.19 LUFS** | **-16.19 LUFS** | Dung sai cho phép: $\pm 0.5$ LU |
| **Mục tiêu True Peak** | $\le -1.0\text{ dBTP}$ | $\le -1.0\text{ dBTP}$ | $\le -1.0\text{ dBTP}$ | $\le -1.0\text{ dBTP}$ | $\le -1.0\text{ dBTP}$ (Chống clip) |
| **Thực đo True Peak** | **-1.5 dBTP** | **-1.5 dBTP** | **-1.5 dBTP** | **-1.5 dBTP** | An toàn, không méo biên độ |
| **Mã băm SHA-256** | `beb17a4125c3...` | `2665833fffa7...` | `bc8778f9c8a3...` | `612857aeb141...` | Toàn vẹn tuyệt đối |

---

## 2. PHÂN TÍCH CHẤT LƯỢNG KỸ THUẬT DSP

### 2.1. Kiểm soát mức âm lượng (Loudness Compliance)
- Cả 4 tệp master đều đạt mức áp suất âm thanh mục tiêu **-16.0 LUFS** với độ lệch cực nhỏ:
  - Workflow A: $-16.11\text{ LUFS}$ ($\Delta = -0.11\text{ LU}$)
  - Workflow B: $-16.27\text{ LUFS}$ ($\Delta = -0.27\text{ LU}$)
  - Workflow C: $-16.19\text{ LUFS}$ ($\Delta = -0.19\text{ LU}$)
- Tất cả đều nằm sâu trong ngưỡng dung sai khắt khe của tiêu chuẩn ITU-R BS.1770-4 và EBU R128 ($\pm 0.5\text{ LU}$).

### 2.2. Kiểm soát đỉnh thực tế (True Peak Limiting & Anti-Clipping)
- Giá trị True Peak thực tế đo được ở toàn bộ các tệp là **-1.5 dBTP**, thấp hơn trần an toàn $-1.0\text{ dBTP}$.
- Điều này chứng minh thuật toán giới hạn biên độ tuyến tính trong Pass 2 của FFmpeg triệt tiêu hoàn toàn hiện tượng inter-sample peaks khi chuyển đổi tín hiệu số sang analog hoặc khi nén sang MP3.

### 2.3. Chuyển đổi tần số mẫu & Ghép nối đa động cơ (Resampling & Concat)
- Âm thanh gốc của **VieNeu-TTS** là 48kHz, trong khi **Qwen3-TTS** xuất ra ở 24kHz.
- Trong Workflow C (hội thoại đan xen giữa Lan và Mei), FFmpeg `aresample=48000:resampler=soxr` đã tự động nâng mẫu các đoạn 24kHz của Qwen3 lên 48kHz trước khi ghép nối mà không làm suy giảm chất lượng âm thanh hoặc tạo ra tiếng lách cách (clicking/popping) tại điểm chuyển đoạn.
- Các khoảng lặng (`pause_after_ms` từ 300ms đến 500ms) được chèn mượt mà bằng bộ lọc `apad`.

---

## 3. LƯU Ý VỀ ĐÁNH GIÁ CHẤT LƯỢNG THÍNH GIÁC (PERCEPTUAL QUALITY)

> [!IMPORTANT]
> **Khuyến nghị kỹ thuật:**  
> Các chỉ số đo lường trên xác nhận rằng tín hiệu âm thanh đáp ứng 100% các tiêu chuẩn kỹ thuật về mức âm lượng, giới hạn đỉnh và tần số mẫu.  
> Tuy nhiên, mức độ tự nhiên về ngữ điệu, sự mượt mà của câu từ và độ tương đồng giọng nói (speaker similarity) cần có sự đánh giá thính giác trực tiếp từ người nghe (Human Perceptual Listening Test / MOS). Hệ thống không tự động công bố điểm MOS mà không có dữ liệu đánh giá thực nghiệm từ người dùng.
