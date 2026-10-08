# AI VOICE STUDIO — GIỚI HẠN KỸ THUẬT ĐÃ BIẾT GIAI ĐOẠN 2 (PHASE 2 KNOWN LIMITATIONS)

**Tác giả:** Principal Backend Engineer & Technical Architect  
**Ngày cập nhật:** 2026-10-08  
**Trạng thái áp dụng:** Giai đoạn 2 Release Gate R1 (Durable Queue & Resilience Remediated)  

---

## 1. DANH MỤC CÁC GIỚI HẠN KỸ THUẬT HIỆN TẠI

### 1.1. Thực thi trên Contract Mock Engine (Chưa tích hợp Neural Adapter)
- **Mô tả:** Hệ thống Phase 2 đã hoàn thiện 100% logic hàng đợi bền vững, bảo vệ giao dịch, thu hồi lease, Fencing Token và streaming sự kiện thời gian thực. Tuy nhiên, toàn bộ luồng xử lý suy luận hiện tại được thực hiện thông qua **Contract Mock Engine** (`engines/mock`).
- **Lý do thiết kế:** Tuân thủ triệt để phân kỳ dự án: Phase 2 tập trung hoàn thiện cơ chế điều phối và chống chịu sự cố (Resilience). Các Engine Adapter sản xuất cho **VieNeu-TTS** (CPU ONNX) và **Qwen3-TTS** (GPU PyTorch) sẽ được hiện thực hóa ở **Phase 3**.

### 1.2. Giới hạn Quy mô Máy đơn Cục bộ (Single-Host SQLite WAL Scope)
- **Mô tả:** Hàng đợi bền vững được tối ưu hóa cho môi trường máy trạm đơn lẻ (Single-host Windows desktop) với SQLite WAL.
- **Hệ quả:** Hệ thống đạt hiệu năng cực cao và không yêu cầu cài đặt dịch vụ trung gian phức tạp (như Redis hay Celery). Tuy nhiên, thiết kế này không hỗ trợ việc mở rộng phân tán ra nhiều máy chủ khác nhau qua mạng LAN (phù hợp với định hướng Local-First Desktop Studio).

### 1.3. Giới hạn Khe Tài nguyên GPU (GPU Slot Concurrency Limit)
- **Mô tả:** Căn cứ vào các kết luận đo đạc phần cứng thực tế ở Phase 1B trên card NVIDIA GeForce RTX 3050 (6GB VRAM), `ResourceManager` đặt giới hạn cứng đa tiến trình dựa trên cơ sở dữ liệu:
  - `max_gpu_slots = 1`
  - `max_cpu_slots = 1`
- **Hệ quả:** Bất kỳ tác vụ GPU nào được gửi đến khi khe GPU đang bận đều phải chờ đợi trong hàng đợi với lý do `Awaiting GPU slot`. Điều này bảo vệ máy tính khỏi nguy cơ CUDA Out-Of-Memory và gián đoạn Windows DWM.

### 1.4. Cơ chế Điều phối Hai Chế độ (Dual-Mode Scheduler)
- **Chế độ Mặc định (Embedded):** Chạy bên trong vòng đời FastAPI (`STUDIO_EMBEDDED_SCHEDULER=true`). Phù hợp cho môi trường phát triển nhanh và đóng gói desktop cục bộ.
- **Chế độ Tiến trình Độc lập (Standalone Runner):** Thiết lập `STUDIO_EMBEDDED_SCHEDULER=false` và kích hoạt `python -m apps.server.src.runner`. Đảm bảo cách ly hoàn toàn tiến trình HTTP gateway khỏi các sự cố suy luận nặng.

### 1.5. Yêu cầu Sao lưu Trực tuyến (SQLite Online Backup Mandatory)
- **Mô tả:** Trong chế độ SQLite WAL, việc sao chép tệp trực tiếp qua OS (`copy` hoặc `shutil`) trong lúc đang ghi có thể dẫn đến việc sao chép dữ liệu chưa hoàn tất checkpoint (torn read).
- **Yêu cầu:** Mọi hoạt động sao lưu và khôi phục phải sử dụng công cụ chuẩn `python -m apps.server.src.backup` (sử dụng SQLite Online Backup API `sqlite3.Connection.backup()`).

### 1.6. Chất lượng Nhân bản Giọng nói Thực tế vẫn ở trạng thái PENDING
- **Mô tả:** Mặc dù pipeline nhân bản giọng đã sẵn sàng tiếp nhận tham số âm thanh tham chiếu, việc thẩm định độ tương đồng người nói (perceptual speaker similarity) đối với mẫu giọng cá nhân cụ thể của người dùng sẽ chỉ được thực hiện khi người dùng tải lên mẫu giọng trên Web UI ở Phase 3.

---

## 2. KẾ HOẠCH GIẢI QUYẾT TẠI GIAI ĐOẠN 3 (PHASE 3 ROADMAP)

1. Triển khai `engines/vieneu-tts` adapter chính thức cho Tiếng Việt (chạy trên CPU qua ONNX Runtime).
2. Triển khai `engines/qwen3-tts` adapter chính thức cho Tiếng Trung (chạy trên GPU qua PyTorch `bfloat16`).
3. Tích hợp Module chuẩn hóa tần số lấy mẫu (Resampler 24kHz / 48kHz).
4. Xây dựng giao diện tải lên tệp âm thanh mẫu để nhân bản giọng đọc cá nhân trực quan.
