# BÁO CÁO NGHIỆM THU KIẾN TRÚC & PHÁT HÀNH PHASE 4
## AI VOICE STUDIO — PROFESSIONAL STUDIO UX, LONG-FORM TTS, DIALOGUE WORKSPACE & AUDIO MASTERING

**Ngày thẩm định:** 08/10/2026  
**Phiên bản hệ thống:** v0.4.0  
**Kiến trúc tham chiếu:** R1.1  
**Vai trò thẩm định:** Principal Software Engineer, Audio DSP Engineer, Security Reviewer, Product QA Lead  
**Kết luận thẩm định (Verdict):** **OFFICIAL PASS (CHÍNH THỨC ĐẠT)**

---

## 1. TỔNG QUAN KẾT QUẢ ĐÁNH GIÁ

Giai đoạn Phase 4 đã chuyển đổi nền tảng **AI Voice Studio** từ một giao diện TTS thô sơ thành một **Workstation sản xuất âm thanh chuyên nghiệp (Professional Audio Production Application)** vận hành cục bộ trên máy trạm Windows.

Toàn bộ các tiêu chí nghiệm thu nghiêm ngặt tại Release Gate đã được chứng minh qua dữ liệu thực tế, âm thanh thực tế và kiểm thử tự động toàn diện:
1. **Kiến trúc dữ liệu bền bỉ & Toàn vẹn bất đồng bộ:** Mô hình hóa hoàn chỉnh 5 bảng mới (`projects`, `characters`, `script_segments`, `segment_revisions`, `project_exports`) với cơ chế kiểm soát tương tranh lạc quan (OCC via `version`) và cơ chế chống ghi đè từ các job kết thúc muộn (Stale Job Overwrite Prevention).
2. **Hệ thống Audio DSP & Mastering đạt chuẩn công nghiệp:** Triển khai quy trình chuẩn hóa âm lượng hai bước (Two-Pass EBU R128 Loudness Normalization), giới hạn đỉnh thực tế True Peak $\le -1.0\text{ dBTP}$, chống nén vỡ (anti-clipping), chuyển đổi tần số mẫu an toàn (aresample) và bảo vệ tuyệt đối chống Command Injection trong `ffconcat` demuxer.
3. **Sinh âm thanh thực tế với 2 Neural TTS Engines:**
   - **VieNeu-TTS v3 Turbo** (CPU ONNX FP32, 48kHz) cho giọng đọc tiếng Việt mượt mà.
   - **Qwen3-TTS 0.6B CustomVoice** (GPU NVIDIA RTX 3050 CUDA, 24kHz) cho giọng đọc tiếng Trung.
   - Hoàn thành đầy đủ 4 workflows sản xuất thực tế (A, B, C, D) với 4 tệp Master WAV và MP3 đạt chuẩn EBU R128 (-16 LUFS).
4. **Hạ tầng kiểm thử toàn diện:** 78/78 tests hồi quy tự động vượt qua (100% PASS), bao gồm Unit, Contract, Security, Integration, và Chrome Browser E2E Tests (Playwright).
5. **Cơ chế sao lưu & Phục hồi:** Kiểm chứng thành công SQLite Online Backup và Restore độc lập không gián đoạn hệ thống.

---

## 2. KẾT QUẢ ĐỐI SOÁT KIẾN TRÚC & MÃ NGUỒN

### 2.1. Quản lý trạng thái và đồng bộ phân đoạn (Segment State Reconciler)
- **Vấn đề đã khắc phục:** Khi người dùng chỉnh sửa văn bản trong lúc một job TTS nền đang tổng hợp, nếu không kiểm tra hash nội dung, job hoàn thành sau có thể ghi đè audio lỗi thời lên văn bản mới và đánh dấu hoàn thành sai lệch.
- **Giải pháp bảo đảm toàn vẹn:** Trong `apps/server/src/services/project_service.py`, hàm `reconcile_project_segments` so khớp `job_hash` của request ban đầu với `seg.text_hash` hiện tại. Nếu không trùng khớp (stale job):
  - Tệp âm thanh cũ được lưu trữ bảo toàn vào lịch sử phân đoạn (`SegmentRevisionRecord`).
  - Phân đoạn hiện tại giữ nguyên trạng thái `draft` hoặc `stale`, không bị ghi đè `active_artifact_id`.

### 2.2. Audio DSP Service & Bảo mật FFmpeg
- **Phát hiện và cấu hình:** Hệ thống tự động xác định `ffmpeg.exe` (v7.1.1 essentials GPLv3) thông qua biến cấu hình `STUDIO_FFMPEG_PATH` hoặc đường dẫn máy trạm.
- **Bảo mật `ffconcat`:** Tệp manifest concat được tạo với cơ chế escape an toàn dấu nháy đơn (`' -> '\''`), đường dẫn tệp được xác thực quyền sở hữu và kiểm tra sự tồn tại trên ổ đĩa trước khi đưa vào manifest.
- **Mastering EBU R128 Hai Bước:**
  - *Pass 1 (Measurement):* Chạy `loudnorm=print_format=json` để đo đạc chính xác `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`.
  - *Pass 2 (Linear Normalization):* Chạy bộ lọc tuyến tính với các thông số đo được, chèn silence (`apad`) theo `pause_after_ms`, đảm bảo độ đồng đều áp suất âm thanh giữa giọng nam/nữ, tiếng Việt và tiếng Trung.
- **Ghi tệp nguyên tử (Atomic File Creation):** Tệp xuất bản được ghi tạm vào `.tmp` và đổi tên nguyên tử (`os.replace`) để tránh tình trạng tệp xuất bản bị đọc dở dang.

---

## 3. THẨM ĐỊNH KẾT QUẢ 4 QUY TRÌNH THỰC TẾ

| Workflow | Mô tả quy trình | Động cơ & Thiết bị | Định dạng & Tần số | Thời lượng | Âm lượng thực tế | True Peak |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Workflow A** | Sách nói tiếng Việt dài (5 câu, chỉnh sửa & tái sinh câu 2) | VieNeu-TTS (CPU) | WAV 48kHz 16-bit | 23.10s | **-16.11 LUFS** | **-1.5 dBTP** |
| **Workflow B** | Kể chuyện tiếng Trung (4 câu Giang Nam) | Qwen3-TTS (GPU) | MP3 48kHz 192kbps | 27.72s | **-16.27 LUFS** | **-1.5 dBTP** |
| **Workflow C (WAV)** | Hội thoại đa nhân vật (Lan & Mei, khoảng lặng 300-500ms) | VieNeu (CPU) + Qwen3 (GPU) | WAV 48kHz 16-bit | 21.63s | **-16.19 LUFS** | **-1.5 dBTP** |
| **Workflow C (MP3)** | Hội thoại đa nhân vật (Lan & Mei, khoảng lặng 300-500ms) | VieNeu (CPU) + Qwen3 (GPU) | MP3 48kHz 192kbps | 21.67s | **-16.19 LUFS** | **-1.5 dBTP** |
| **Workflow D** | Tải lại và kiểm tra toàn vẹn sau khởi động lại | N/A | Toàn bộ 12 bảng SQLite | Đạt | Toàn vẹn 100% | Đạt |

*Tất cả các tệp âm thanh thực tế đã được sao lưu và lưu trữ tại:* `D:\AIVoiceStudioData\acceptance_audio_phase4\`

---

## 4. RANH GIỚI KIẾN TRÚC & QUYỀN HẠN

- **Phạm vi hoàn tất:** Phase 4 đã hoàn thành đầy đủ, đáp ứng mọi yêu cầu của Product Specification và Architecture R1.1.
- **Quy tắc nghiêm ngặt:**
  - **TUYỆT ĐỐI KHÔNG BẮT ĐẦU PHASE 5.**
  - Không mở port LAN/Internet, giữ nguyên chính sách liên kết mạng cục bộ an toàn (`127.0.0.1`).
  - Không thay đổi cấu hình tường lửa hay mở rộng hạ tầng ngoài máy trạm đơn lẻ.
