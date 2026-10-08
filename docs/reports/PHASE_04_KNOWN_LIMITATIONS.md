# AI VOICE STUDIO — PHASE 4 KNOWN LIMITATIONS & SYSTEM BOUNDARIES
## GIỚI HẠN KỸ THUẬT ĐÃ BIẾT VÀ RANH GIỚI HỆ THỐNG

**Phiên bản**: Phase 4 Baseline  
**Ngày lập**: 2026-10-08  
**Tình trạng**: Đã ghi nhận và kiểm soát trong thiết kế kiến trúc.

---

### 1. GIỚI HẠN VỀ ĐÁNH GIÁ CHẤT LƯỢNG GIỌNG SAO CHÉP (VOICE SIMILARITY)
- **Ranh giới**: Hệ thống xác thực tính toàn vẹn của tệp âm thanh (định dạng WAV/MP3, không bị ngắt quãng, tần số mẫu chuẩn, âm lượng EBU R128), nhưng **KHÔNG** tuyên bố hay khẳng định chất lượng cảm thụ (Perceptual Quality) hoặc độ tương đồng tuyệt đối của giọng sao chép (Speaker Similarity) khi chưa có bài đánh giá thính lực của con người (Human MOS - Mean Opinion Score Evaluation).
- **Khuyến nghị vận hành**: Các sản phẩm sách nói hoặc kịch truyền thanh trước khi phát hành thương mại cần được kỹ sư âm thanh nghe kiểm thử chất lượng thực tế.

---

### 2. HIỆU NĂNG XỬ LÝ DSP VÀ GHÉP NỐI TRÊN DỰ ÁN DÀI (FFMPEG DSP LATENCY)
- **Ranh giới**: Việc ghép nối âm thanh sử dụng FFmpeg 7.1.1 qua tệp manifest tạm thời (`concat -f concat -safe 0`) giúp vượt qua giới hạn độ dài dòng lệnh Windows (Windows CommandLine 8191-character limit). Tuy nhiên:
  - Bộ lọc chuẩn hóa âm lượng hai lượt (Two-pass EBU R128 loudnorm) và chuyển đổi tần số mẫu chất lượng cao (SOXR Resampler) chạy trên CPU.
  - Với một chương sách dài trên 30 phút (hơn 150 phân đoạn), quá trình xuất file Master có thể mất từ 10 đến 30 giây CPU.
- **Biện pháp xử lý**: Giao diện hiển thị trạng thái xử lý rõ ràng ("Đang xử lý DSP & Ghép nối FFmpeg...") và backend chạy tác vụ subprocess trong timeout an toàn (300 giây).

---

### 3. GIAO DIỆN PHÁT ÂM THANH VÀ TIMELINE SCRUBBING
- **Ranh giới**: Trong Phase 4, hệ thống cung cấp trình phát âm thanh mini (Mini Audio Player) cho từng phân đoạn và cho phép nghe trước các bản thu lịch sử (`SegmentRevision`). Hệ thống hiện chưa tích hợp timeline kéo thả đa rãnh (Multi-track DAW timeline) hoặc hiển thị dạng sóng tương tác thời gian thực (Interactive Waveform Canvas Scrubbing) vốn thuộc phạm vi mở rộng chuyên sâu.
- **Giải pháp thay thế**: Người dùng có thể nghe kiểm tra từng câu thoại trực tiếp trên giao diện và tải về bản Master WAV/MP3 để biên tập trên các phần mềm DAW chuyên dụng (như Audacity, Adobe Audition, Reaper).

---

### 4. ĐỊNH LƯỢNG TÀI NGUYÊN PHẦN CỨNG VÀ TRÁNH CUDA OOM
- **Ranh giới**: Máy trạm phát triển trang bị Intel Core i5-12400F, 16GB RAM và NVIDIA GeForce RTX 3050 (6GB VRAM).
- **Chính sách**:
  - Động cơ Qwen3-TTS tiêu thụ khoảng 3.8GB VRAM trên RTX 3050.
  - Bộ lập lịch (`Scheduler` / `ResourceManager`) duy trì nghiêm ngặt cơ chế hạn mức **1 tác vụ GPU tại một thời điểm** (`max_gpu_slots = 1`). Không cho phép nhiều tiến trình GPU chạy song song nhằm triệt tiêu hoàn toàn nguy cơ tràn bộ nhớ CUDA Out-Of-Memory.
  - Động cơ VieNeu-TTS chạy trên CPU, tận dụng các nhân Intel Core i5 và phân bổ độc lập với GPU.

---

### 5. AN TOÀN TRUY CẬP VÀ PHẠM VI BẢO MẬT (LOCAL-FIRST ONLY)
- **Ranh giới**: Ứng dụng tuân thủ nghiêm ngặt mô hình Local-First:
  - Chỉ lắng nghe trên giao diện cục bộ `127.0.0.1`.
  - Nghiêm cấm mở cổng lắng nghe mạng LAN (`0.0.0.0`) hoặc phơi bày ra Internet trong Phase 4.
  - Mọi thao tác quản trị, dự án và tổng hợp TTS đều yêu cầu xác thực JWT Bearer Token qua header `Authorization: Bearer <token>`.
  - Riêng endpoint tải tệp Master Audio (`/api/v1/projects/exports/{id}/download`), hệ thống hỗ trợ tham số truy vấn an toàn `?token=<jwt>` độc quyền cho thao tác nhấp tải xuống của thẻ liên kết HTML `<a>` phía trình duyệt (do thẻ `<a download>` không thể gửi kèm HTTP headers tùy biến). Tham số này được kiểm tra quyền sở hữu tệp nghiêm ngặt và không áp dụng cho các API nghiệp vụ khác.

---

### 6. PHÂN BIỆT THIẾT LẬP DSP MASTERING: PRESET PODCAST/WEB (-16 LUFS) VS PHÁT THANH EBU R128 (-23 LUFS)
- **Ranh giới định lượng**:
  - Giá trị mặc định `-16.0 LUFS` trên giao diện Master Export Modal là **Preset Chuẩn Hóa Trực Tuyến** dành riêng cho Podcast, YouTube và Sách nói trực tuyến (theo khuyến nghị AES TD1004 và Apple Podcasts), sử dụng thuật toán đo lường ITU-R BS.1770 / EBU R128 `loudnorm` của FFmpeg.
  - Tiêu chuẩn phát thanh truyền hình truyền thống của Liên minh Phát thanh Truyền hình Châu Âu (**EBU R128 Broadcast Standard**) quy định mức mục tiêu là **-23.0 LUFS** (sai số cho phép $\pm 0.5$ LU). Giao diện và API cung cấp tùy chọn `-23.0 LUFS` cho người dùng sản xuất chương trình truyền hình/phát thanh.
- **Giới hạn đỉnh (Peak Limiting & Intersample Clipping)**:
  - Ngưỡng True Peak limiter ceiling được cấu hình ở mức **-1.5 dBTP** (`TP=-1.5`) nhằm tạo khoảng dự trữ an toàn (headroom) 1.5 dB, giúp ngăn ngừa và triệt tiêu đáng kể hiện tượng méo đỉnh liên mẫu (intersample clipping).
  - Hệ thống **KHÔNG** tuyên bố việc méo tiếng là "hoàn toàn bất khả thi về mặt toán học" dưới mọi định dạng nén lossy MP3 hoặc các bộ giải mã DAC khác nhau, nhưng mức -1.5 dBTP đã bảo đảm tiêu chuẩn an toàn cao theo thông lệ kỹ thuật âm thanh chuyên nghiệp.

