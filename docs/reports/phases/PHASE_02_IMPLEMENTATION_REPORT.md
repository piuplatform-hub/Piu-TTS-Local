# AI VOICE STUDIO — BÁO CÁO TRIỂN KHAI GIAI ĐOẠN 2 (PHASE 2 IMPLEMENTATION REPORT)
## HÀNG ĐỢI BỀN VỮNG & NĂNG LỰC CHỐNG CHỊU SỰ CỐ (DURABLE JOB ORCHESTRATION & PRODUCTION RESILIENCE)

**Tác giả:** Principal Backend Engineer, Software Architect, QA Lead  
**Ngày hoàn thành:** 2026-10-08  
**Trạng thái phê duyệt:** ĐÃ TRIỂN KHAI & VƯỢT QUA TOÀN BỘ 28/28 BÀI KIỂM THỬ (100% PASS)  
**Môi trường thực thi:** Windows 11 / Intel Core i5-12400F / NVIDIA RTX 3050 6GB / SQLite 3 WAL  

---

## 1. TỔNG QUAN KẾT QUẢ GIAI ĐOẠN 2

Giai đoạn 2 đã nâng cấp hoàn chỉnh hạ tầng xử lý tác vụ của AI Voice Studio từ mô hình background task tức thời sang **Hàng đợi bền vững chuẩn giao dịch (Transactional Durable Queue)** kết hợp **Fencing Tokens**, **Bộ lập lịch độc lập (Independent Scheduler Daemon)**, **Kiểm soát tài nguyên phần cứng (Resource Slots)**, và **Luồng sự kiện thời gian thực (Server-Sent Events - SSE)**.

Hệ thống tiếp tục vận hành trên nền tảng **Contract Mock Engine** (`engines/mock`) độc lập, bảo đảm kiểm định toàn diện các tình huống gián đoạn, sập nguồn, quá tải bộ nhớ và xung đột khóa mà không tiêu tốn tài nguyên suy luận nặng trước Phase 3.

---

## 2. CÁC THÀNH PHẦN KIẾN TRÚC ĐÃ TRIỂN KHAI

### 2.1. Lược đồ Cơ sở dữ liệu & Di chuyển Alembic (Database Schema Migration)
- **Sao lưu an toàn:** Đã tạo bản sao lưu vật lý của cơ sở dữ liệu Phase 1 tại `D:\AIVoiceStudioData\studio.db.phase1.bak` và `D:\AIVoiceStudioData\backups\studio.db.phase1.bak`.
- **Alembic Migration (`alembic/versions/20261008_0002_durable_jobs.py`):**
  - Chạy ở chế độ SQLite Batch Alter Mode (`render_as_batch=True`).
  - Bổ sung các cột cho bảng `jobs`:
    - `priority`: Mức độ ưu tiên của tác vụ (INTEGER, mặc định `0`).
    - `resource_type`: Phân loại tài nguyên (`cpu` hoặc `gpu`, mặc định `cpu`).
    - `attempt_count`: Số lần đã cố gắng xử lý (INTEGER, mặc định `0`).
    - `max_retries`: Giới hạn thử lại tối đa (INTEGER, mặc định `3`).
    - `current_attempt_id`: Fencing Token dạng UUID (VARCHAR 36).
    - `locked_by`: Định danh worker/scheduler đang giữ khóa (VARCHAR 100).
    - `scheduled_at`: Thời điểm dự kiến thực thi lại khi backoff (DATETIME).
    - `waiting_reason`: Lý do tác vụ phải chờ (VARCHAR 255).
    - Chỉ mục tổ hợp: `ix_jobs_queue_order` trên `(status, priority, queued_at)`.
  - Tạo bảng `job_events`:
    - `id`: Khóa chính tự tăng (INTEGER PRIMARY KEY).
    - `job_id`: Khóa ngoại trỏ đến `jobs.id` (ON DELETE CASCADE).
    - `event_type`: Loại sự kiện (`status_change`, `progress`, `heartbeat`, `completed`, `failed`, `cancelled`).
    - `data`: Payload chi tiết (JSON).
    - `created_at`: Dấu thời gian (DATETIME UTC).
    - Chỉ mục: `ix_job_events_job_id_id` trên `(job_id, id)`.

### 2.2. Máy trạng thái tác vụ (Durable Job State Machine)
- Triển khai trong `apps/server/src/services/job_state_machine.py`.
- Định nghĩa 6 trạng thái minh định: `queued`, `preparing`, `running`, `completed`, `failed`, `cancelled`.
- Ngăn chặn nghiêm ngặt các chuyển đổi bất hợp pháp bằng ngoại lệ `IllegalStateTransitionError` (trả về HTTP 400 Problem Details RFC 9457).
- Ngăn chặn triệt để tình trạng zombie task hoặc hoàn tất job đã bị hủy.

### 2.3. Hàng đợi Giao dịch & Fencing Token (Durable Queue Service)
- Triển khai trong `apps/server/src/services/durable_queue_service.py`.
- **Atomic Job Claiming:** Sử dụng câu lệnh UPDATE có điều kiện kết hợp bộ lọc tài nguyên khả dụng, bảo đảm 10 worker cạnh tranh đồng thời chỉ có duy nhất 1 worker nhận được tác vụ.
- **Short Transactions:** Giao dịch SQLite được commit ngay lập tức sau khi claim, gia hạn heartbeat hoặc hoàn tất. Quá trình tổng hợp âm thanh của worker diễn ra hoàn toàn ngoài transaction, loại bỏ triệt để lỗi khóa SQLite (`OperationalError: database is locked`).
- **Fencing Token Validation:** Mỗi lượt claim sinh ra một `current_attempt_id` duy nhất. Mọi worker cũ cố tình hoàn tất sau khi lease đã hết hạn đều bị từ chối với ngoại lệ `FencingTokenError` (HTTP 409), bảo vệ tính toàn vẹn của artifact.
- **Xử lý xung đột Idempotency (409 Conflict):** Khi client gửi lại cùng một `idempotency_key` nhưng payload khác nhau, hệ thống trả về mã lỗi `409 Conflict` (mã lỗi `IDEMPOTENCY_CONFLICT`).

### 2.4. Trình Lập Lịch Độc Lập (Independent Scheduler Daemon)
- Triển khai trong `apps/server/src/supervisor/scheduler.py`.
- Thay thế hoàn toàn cơ chế `FastAPI BackgroundTasks` bằng vòng lặp nền bất đồng bộ quản lý trong `lifespan` của FastAPI.
- Tự động quét và thu hồi các lease quá hạn (Lease Expiration Reclaim) theo thuật toán lũy thừa lùi dần: `delay = 2.0 * (2 ** (attempt - 1))`.
- Quản lý vòng đời worker: gửi heartbeat ngầm định kỳ 5 giây để gia hạn lease 30 giây trong khi worker đang tổng hợp.

### 2.5. Phục Hồi Sự Cố Khi Khởi Động (Crash & Restart Recovery)
- Khi server FastAPI khởi động, Scheduler quét toàn bộ các tác vụ bị kẹt ở trạng thái `preparing` hoặc `running` do sập nguồn máy chủ đột ngột.
- Nếu `attempt_count < max_retries`, tự động đưa về `queued` với ghi chú `Recovered after server restart`.
- Nếu đã vượt quá `max_retries`, chuyển sang `failed` với mã lỗi `SERVER_RESTARTED`.

### 2.6. Bộ Phân Bổ Tài Nguyên Phòng Thủ (Resource Slot Allocator)
- Triển khai trong `apps/server/src/services/resource_manager.py`.
- Giới hạn cứng tối đa: `max_gpu_slots = 1` (phù hợp với card RTX 3050 6GB theo kết luận Phase 1B), `max_cpu_slots = 1`, `max_global_slots = 2`.
- Khi khe GPU bị chiếm, tác vụ GPU tiếp theo tiếp tục ở trạng thái `queued` và cập nhật thông điệp `Awaiting GPU slot` trên giao diện.

### 2.7. Luồng Sự Kiện Thời Gian Thực (Server-Sent Events - SSE)
- Triển khai trong `apps/server/src/services/event_service.py` và endpoint `GET /api/v1/jobs/{job_id}/events`.
- Lưu trữ bền vững toàn bộ sự kiện vào bảng `job_events`.
- Hỗ trợ client tái kết nối và phát lại sự kiện bị bỏ lỡ thông qua header `Last-Event-ID` hoặc query parameter `?last_event_id=`.
- Hỗ trợ xác thực qua query parameter `?token=...` dành riêng cho chuẩn trình duyệt `EventSource`.
- Cơ chế Fallback tự động sang REST Polling trên giao diện nếu môi trường mạng chặn SSE.

### 2.8. Tích hợp Giao diện Web (Frontend Integration)
- **Cập nhật Types & API Client (`apps/web/src/api/client.ts`):** Bổ sung `cancelJob`, `retryJob`, và `connectJobEvents` với cơ chế lắng nghe SSE tự khôi phục.
- **Speech Studio View (`apps/web/src/components/StudioView.tsx`):**
  - Hiển thị đầy đủ 6 trạng thái kèm huy hiệu và màu sắc đặc trưng.
  - Hiển thị chỉ báo kết nối thời gian thực `SSE Live`.
  - Nút **Hủy tác vụ (Cancel)** khi job đang ở `queued`, `preparing`, hoặc `running`.
  - Nút **Thử lại (Retry)** khi job gặp lỗi `failed`.
  - Lưu mã job đang xử lý vào `localStorage` và tự động khôi phục luồng SSE khi người dùng tải lại trang (F5).
- **Lịch sử Tác Vụ (`apps/web/src/components/JobHistoryTable.tsx`):**
  - Hiển thị chi tiết số lần thử lại (`lần X`), lý do chờ hàng đợi.
  - Cho phép hủy hoặc thử lại tác vụ trực tiếp từ bảng lịch sử.
- **Biên dịch Production:** Đã biên dịch sạch sẽ không cảnh báo (`tsc && vite build`) với dung lượng bundle tối ưu.

---

## 3. TỔNG KẾT TUÂN THỦ KIẾN TRÚC (ARCHITECTURAL COMPLIANCE)

| Quyết định Kiến trúc (ADR) | Trạng thái Phase 2 | Minh chứng thực tế |
|:---|:---:|:---|
| **ADR-0001: API-First Headless Core** | **Tuân thủ 100%** | Toàn bộ trạng thái hàng đợi và SSE đều truy cập độc lập qua chuẩn REST/SSE API |
| **ADR-0002: Modular Monolith** | **Tuân thủ 100%** | Phân tầng chặt chẽ: `services/durable_queue_service`, `services/resource_manager`, `supervisor/scheduler` |
| **ADR-0003: SQLite WAL Mode** | **Tuân thủ 100%** | Giao dịch ngắn, không giữ lock khi suy luận, xử lý đồng thời qua WAL |
| **ADR-0004: Isolated Inference Workers** | **Tuân thủ 100%** | Scheduler giao tiếp worker qua HTTP loopback, Windows Job Object kiểm soát |
| **ADR-0005: Local Storage & Security** | **Tuân thủ 100%** | Token xác thực qua query param được giải mã an toàn, quyền sở hữu job được bảo vệ |
| **ADR-0006: Hardware Coexistence** | **Tuân thủ 100%** | Resource Manager bảo đảm không bao giờ chạy quá 1 GPU job trên card RTX 3050 |
