# NHẬT KÝ SỬA ĐỔI VÀ KHẮC PHỤC PHASE 4 RELEASE GATE
## AI VOICE STUDIO — CODE AUDIT, DSP HARDENING & ASYNC DATA INTEGRITY REMEDIATION

**Ngày hoàn thành:** 08/10/2026  
**Mục tiêu:** Giải quyết triệt để các rủi ro kỹ thuật, đảm bảo toàn vẹn dữ liệu bất đồng bộ và kiểm chứng âm thanh thực tế trước khi phê duyệt chính thức Phase 4.

---

## 1. DANH SÁCH CÁC THAY ĐỔI MÃ NGUỒN (SOURCE CODE REMEDIATIONS)

### 1.1. Audio DSP Service (`apps/server/src/services/audio_dsp_service.py`)
- **Tích hợp đường dẫn FFmpeg linh hoạt:** Hỗ trợ biến cấu hình `STUDIO_FFMPEG_PATH` trong `config.py` và `.env`, tự động fallback sang `PATH` hoặc các thư mục chuẩn trên host Windows.
- **Xác thực năng lực bộ xử lý DSP (`verify_ffmpeg_capabilities`):** Kiểm tra phiên bản FFmpeg (v7.1.1 essentials GPLv3), xác nhận đầy đủ các bộ lọc (`loudnorm`, `aresample`, `apad`, `concat`) và bộ giải mã (`pcm_s16le`, `libmp3lame`).
- **Triển khai chuẩn hóa EBU R128 Hai Bước (Two-Pass Normalization):**
  - Bước 1: Trích xuất tham số đo lường (`measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`) qua bộ lọc null.
  - Bước 2: Chuẩn hóa biên độ tuyến tính, hạn chế hiện tượng méo tiếng do dynamic compression.
- **Bảo toàn tần số mẫu MP3:** Thêm tường minh cờ `-ar <sample_rate>` cho bộ mã hóa `libmp3lame` để ngăn FFmpeg tự động ép về 44.1kHz.
- **Bảo mật Concat Demuxer:** Escape ký tự đặc biệt trong đường dẫn manifest (`path.replace("'", "'\\''")`) và kiểm tra quyền sở hữu tệp nguồn của người dùng.
- **Hàm đo lường chỉ số thực tế (`measure_audio_metrics`):** Đo đạc tự động kích thước tệp, mã SHA-256, thời lượng, tần số, số kênh, bit depth, Integrated LUFS và True Peak dBTP.
- **Ghi tệp nguyên tử (Atomic file swap):** Xuất bản âm thanh thông qua tệp `.tmp` tạm thời và hoán đổi bằng `os.replace` để tránh race condition khi đọc tệp.

### 1.2. Tính toàn vẹn dữ liệu bất đồng bộ (`apps/server/src/services/project_service.py`)
- **Sửa trường Payload:** Khắc phục truy cập thuộc tính sai (`job.request_payload` $\rightarrow$ `job.payload_data`).
- **Ngăn chặn ghi đè từ Job kết thúc muộn (Stale Job Overwrite Prevention):** So khớp hash nội dung (`job_hash == seg.text_hash`). Nếu người dùng đã sửa văn bản mới trong khi job cũ đang chạy, âm thanh của job cũ sẽ được lưu an toàn vào `SegmentRevisionRecord`, không ghi đè phân đoạn hiện tại.
- **Đảm bảo cờ cập nhật:** Đảm bảo `changed = True` được bật khi bảo tồn bản thu cũ, kích hoạt `session.commit()` đầy đủ vào database.
- **Khắc phục lỗi MissingGreenlet:** Tải an toàn thuộc tính quan hệ trong SQLAlchemy async mà không kích hoạt lazy load bất hợp lệ.

### 1.3. Mô hình dữ liệu phân đoạn (`apps/server/src/models/segment.py`)
- Thiết lập `lazy="selectin"` cho quan hệ `active_artifact` và `last_job` để bảo đảm truy vấn async không xung đột với event loop.

### 1.4. Giao diện người dùng Web Studio (`apps/web/src/components/`)
- `SpeechStudioView.tsx` & `DialogueStudioView.tsx`: Tích hợp cơ chế tự động thăm dò (auto-polling mỗi 2 giây) khi có các phân đoạn đang kết xuất (`queued` / `rendering`), tự động cập nhật trạng thái khi hoàn tất.
- Build production bundle thành công 100% với Vite, không phát sinh lỗi TypeScript.

---

## 2. KIỂM THỬ VÀ XÁC THỰC BỔ SUNG

1. **Bộ kiểm thử tính toàn vẹn dữ liệu:** `tests/integration/test_phase4_data_integrity.py` (4/4 PASSED).
2. **Kịch bản sản xuất âm thanh thực tế:** `scripts/generate_phase4_acceptance_audio.py` (Hoàn thành 4 workflows A, B, C, D trên VieNeu CPU và Qwen3 GPU).
3. **Bộ kiểm thử E2E trên Google Chrome:** `tests/e2e/test_phase4_browser_e2e.py` (Hoàn thành 100% các hành trình Studio).
4. **Bản sao lưu SQLite:** Tạo thành công `D:\AIVoiceStudioData\backups\studio_20261008_154951.db` và kiểm chứng khôi phục thành công.
