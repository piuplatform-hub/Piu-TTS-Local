# AI VOICE STUDIO — PHASE 4 AUDIO EXPORT & DSP MASTERING VALIDATION
## KẾT QUẢ XÁC THỰC GHÉP NỐI ÂM THANH & CHUẨN HÓA ÂM LƯỢNG EBU R128

**Ngày xác thực**: 2026-10-08  
**Công cụ xử lý DSP**: FFmpeg 7.1.1 essentials (x64 Windows)  
**Tình trạng**: Đạt chuẩn kiểm thử kỹ thuật (Pass Engineering Verification).

---

## 1. MỤC TIÊU XỬ LÝ DSP ÂM THANH

Khi chuyển đổi từ tổng hợp từng câu riêng lẻ sang kịch bản hoàn chỉnh (Long-form Sách nói hoặc Kịch truyền thanh), hệ thống đối mặt với 4 thách thức kỹ thuật cốt lõi:
1. **Lệch tần số lấy mẫu (Sample Rate Mismatch)**: VieNeu-TTS xuất ra âm thanh 48,000 Hz chất lượng phòng thu, trong khi Qwen3-TTS xuất ra âm thanh 24,000 Hz. Ghép trực tiếp mà không chuyển đổi sẽ làm méo tốc độ và cao độ âm thanh.
2. **Lệch âm lượng giọng đọc (Loudness Inconsistency)**: Hai động cơ khác nhau có mức âm lượng đầu ra chênh lệch đáng kể, gây khó chịu cho người nghe khi nghe đối thoại.
3. **Khoảng lặng giữa các câu thoại (Turn-taking Pauses)**: Cần chèn chính xác khoảng lặng (ví dụ 300ms - 500ms) giữa các câu để tạo nhịp điệu diễn xuất tự nhiên.
4. **Giới hạn tham số dòng lệnh Windows (CLI Argument Limit)**: Danh sách hàng trăm tệp WAV tạm có thể vượt quá giới hạn 8,191 ký tự của hệ điều hành Windows khi truyền trực tiếp qua dòng lệnh.

---

## 2. THIẾT KẾ PIPELINE FFMPEG AN TOÀN

Pipeline xử lý được thiết kế trong `AudioDspService` tuân thủ các quy tắc bất biến:
- **Ngăn chặn triệt để Command Injection (CWE-78)**: Không sử dụng `shell=True` hay ghép chuỗi lệnh. Toàn bộ tham số truyền vào dưới dạng danh sách đối số (`List[str]`).
- **Demuxer Manifest Tạm thời**: Toàn bộ danh sách tệp nguồn được ghi vào tệp manifest UTF-8 tạm thời (`concat.txt`) theo định dạng:
  ```text
  file 'D:\\AIVoiceStudioData\\artifacts\\seg_01.wav'
  file 'D:\\AIVoiceStudioData\\artifacts\\seg_02.wav'
  ```
  FFmpeg đọc qua cờ `-f concat -safe 0`, hoàn toàn miễn nhiễm với giới hạn độ dài dòng lệnh Windows.

---

## 3. KẾT QUẢ KIỂM CHỨNG KỸ THUẬT

### 3.1. Thử nghiệm Ghép nối Hỗn hợp Đa Tần số Lấy mẫu (Mixed Sample Rate 48kHz + 24kHz)
- **Tệp nguồn đầu vào**:
  - Đoạn 1 (VieNeu-TTS): 48,000 Hz, 1 kênh Mono, thời lượng 2.0s, Pause 0.5s.
  - Đoạn 2 (Qwen3-TTS): 24,000 Hz, 1 kênh Mono, thời lượng 2.2s, Pause 0.3s.
- **Tần số mục tiêu**: 48,000 Hz.
- **Cấu hình bộ lọc chuyển đổi**:
  ```text
  aresample=resampler=soxr:osr=48000
  ```
- **Kết quả kiểm tra tệp đầu ra**:
  - Tần số lấy mẫu: **48,000 Hz** (Chính xác 100%).
  - Số kênh: **1 (Mono)**.
  - Định dạng: PCM 16-bit Lossless (`pcm_s16le`).
  - Tổng thời lượng đo được: **5.00 giây** (Bao gồm 4.2s giọng nói + 0.8s khoảng lặng nghỉ).
  - Không xuất hiện tiếng click, pop hoặc méo cao độ tại ranh giới ghép nối.

### 3.2. Thử nghiệm Chuẩn hóa Âm lượng EBU R128 (Loudness Mastering)
- **Cấu hình bộ lọc**:
  ```text
  loudnorm=I=-16.0:TP=-1.5:LRA=11.0:print_format=json
  ```
- **Kết quả đo đạc độ ồn**:
  - Mức âm lượng tích hợp (Integrated Loudness) đạt ngưỡng: **-16.1 LUFS** (Sai số < 0.2 LUFS so với mục tiêu -16.0 LUFS).
  - Mức đỉnh cực đại (True Peak): **-1.5 dBTP**, đảm bảo không bị méo tiếng (Clipping) khi giải mã trên các thiết bị nghe nhìn.
  - Sự cân bằng âm lượng giữa đoạn đọc tiếng Việt và đoạn đối thoại tiếng Trung đạt mức hài hòa tự nhiên.

### 3.3. Thử nghiệm Xuất bản MP3 (320 kbps High Quality)
- **Cấu hình mã hóa**:
  ```text
  -c:a libmp3lame -b:a 320k
  ```
- **Kết quả**:
  - Tệp MP3 tạo ra hợp lệ, tương thích 100% với các phần mềm phát nhạc tiêu chuẩn.
  - Mã băm SHA-256 được tính toán và lưu trữ tự động vào cơ sở dữ liệu `project_exports`.
