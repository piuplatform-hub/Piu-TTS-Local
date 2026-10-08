# AI VOICE STUDIO — BÁO CÁO KIỂM TOÁN VÀ KHẮC PHỤC PHASE 1 (PHASE 1 REVIEW & REMEDIATION REPORT)

**Tác giả:** Senior Software Engineer, Security Reviewer & QA Lead  
**Ngày thực hiện:** 2026-10-08  
**Trạng thái phán quyết ban đầu:** CONDITIONAL PASS  
**Trạng thái phán quyết sau khắc phục:** **PASS (Đủ điều kiện đóng Phase 1)**  

---

## 1. TỔNG QUAN VÀ MỤC ĐÍCH KIỂM TOÁN

Báo cáo này ghi nhận toàn bộ quá trình kiểm toán mã nguồn độc lập, phát hiện lỗ hổng, sửa chữa kỹ thuật và tái kiểm định thực tế đối với Giai đoạn Phase 1 (Foundation & First Vertical Slice) của hệ thống **AI Voice Studio**.

Quá trình kiểm toán tập trung vào tính trung thực kỹ thuật, độ an toàn bảo mật, tính bền vững của cơ sở dữ liệu, khả năng cô lập tiến trình của Worker Supervisor và trải nghiệm người dùng thực tế trên trình duyệt Google Chrome thông qua Playwright.

---

## 2. KẾT QUẢ KIỂM TOÁN MÃ NGUỒN VÀ CÁC ĐIỂM SỬA CHỮA CHÍNH

### 2.1. Quản lý Di chuyển Schema Cơ sở dữ liệu (Alembic Migrations)
- **Vấn đề phát hiện:** Ban đầu, hệ thống chỉ sử dụng `Base.metadata.create_all` trực tiếp trong runtime FastAPI, thiếu hệ thống versioning schema tự động thông qua Alembic theo đúng cam kết ADR-0004.
- **Biện pháp khắc phục đã thực hiện:**
  - Khởi tạo cấu hình di chuyển chuẩn: `alembic.ini` (với cấu hình đường dẫn tương thích đa nền tảng `path_separator = os`).
  - Xây dựng `alembic/env.py` hỗ trợ SQLite WAL, Async Engine (`sqlite+aiosqlite`) và chế độ `render_as_batch=True` để xử lý các hạn chế DDL của SQLite.
  - Tạo bản migration đầu tiên: `alembic/versions/20261008_0001_initial_schema.py` định nghĩa 4 bảng chuẩn (`users`, `engines`, `artifacts`, `jobs`) với cơ chế kiểm tra sự tồn tại (idempotent inspection) đảm bảo nâng cấp an toàn không gây mất mát dữ liệu đối với DB đã tồn tại.
  - Tích hợp `run_migrations()` vào quy trình khởi động server `apps/server/src/database.py`.
  - Kiểm thử: Đã xây dựng và thông qua 4 kiểm thử tự động trong `tests/integration/test_migrations.py` (khởi tạo DB mới, nâng cấp DB cũ giữ nguyên dữ liệu, kiểm tra bật foreign keys, kiểm tra kích hoạt SQLite WAL).

### 2.2. Kiểm soát Vòng đời và Cô lập Tiến trình (Worker Supervisor & Windows Job Objects)
- **Vấn đề phát hiện:** Tiến trình worker con chạy bằng `subprocess.Popen`. Mặc dù có vòng lặp heartbeat và xử lý bắt tín hiệu SIGTERM, trên hệ điều hành Windows, nếu tiến trình cha (FastAPI server) bị buộc dừng đột ngột (killed/crashed), các tiến trình con Python có nguy cơ trở thành zombie process chiếm dụng cổng mạng loopback.
- **Biện pháp khắc phục đã thực hiện:**
  - Trong `apps/server/src/supervisor/supervisor.py`, tích hợp trực tiếp Windows Job Object thông qua Windows Win32 API (`ctypes.windll.kernel32`).
  - Gán cờ `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (giá trị hex `0x2000`) vào Job Object. Khi tiến trình cha đóng hoặc bị tắt, Windows Kernel tự động hủy tất cả các tiến trình con được gán trong Job Object, ngăn chặn triệt để rò rỉ tiến trình zombie.
  - Bổ sung cơ chế fallback mềm dẻo nếu chạy trên các môi trường không phải Windows.
  - Đã kiểm chứng khả năng tự động khôi phục và cô lập tiến trình khi worker gặp sự cố sập (`tests/integration/test_supervisor_resilience.py`).

### 2.3. Cải tiến Xử lý Tham chiếu Cơ sở dữ liệu Lifespan
- **Vấn đề phát hiện:** Khi kiểm thử E2E với cơ sở dữ liệu tạm thời cô lập, `main.py` ban đầu import trực tiếp `AsyncSessionLocal` tại thời điểm load module, dẫn đến việc engine service sử dụng phiên kết nối cũ thay vì phiên kết nối test DB.
- **Biện pháp khắc phục:** Cập nhật `apps/server/src/main.py` sử dụng tham chiếu động `database.AsyncSessionLocal`, đảm bảo mọi môi trường kiểm thử và môi trường chạy thực đều trỏ chính xác vào kết nối cơ sở dữ liệu được cấu hình.

### 2.4. Tính Minh bạch Giao diện Người dùng (Frontend Disclaimer)
- **Vấn đề phát hiện:** Giao diện người dùng cần cảnh báo minh bạch để tránh hiểu lầm rằng âm thanh được sinh ra là từ mạng nơ-ron thực tế.
- **Biện pháp khắc phục:**
  - Cập nhật `apps/web/src/components/StudioView.tsx`, bổ sung biểu ngữ cảnh báo rõ ràng:
    `CONTRACT TEST — Âm thanh tổng hợp kiểm thử hợp đồng PCM 16-bit. Chưa nạp trọng số AI neural (VieNeu/Qwen3).`
  - Biên dịch lại toàn bộ bundle frontend (`npm run build` -> `apps/web/dist`) và kiểm chứng qua SPA server serving.

---

## 3. TỔNG HỢP KIỂM THỬ HỆ THỐNG

Toàn bộ 14 kiểm thử tự động của hệ thống đều vượt qua 100%:

| STT | Tệp kiểm thử | Hạng mục kiểm thử | Kết quả | Thời gian |
|:---:|:---|:---|:---:|:---:|
| 1 | `tests/contract/test_mock_engine.py` | Kiểm định schema Engine Manifest & RFC 9457 errors | **PASSED** | ~0.15s |
| 2 | `tests/contract/test_mock_engine.py` | Vòng đời Mock Worker & sinh âm thanh WAV chuẩn PCM | **PASSED** | ~0.40s |
| 3 | `tests/e2e/test_browser_e2e.py` | Hành trình 12 bước trình duyệt Google Chrome thực tế (Playwright) | **PASSED** | ~5.34s |
| 4 | `tests/integration/test_auth_api.py` | Vòng đời Onboarding, xác thực JWT & chống lặp bootstrap | **PASSED** | ~0.15s |
| 5 | `tests/integration/test_jobs_api.py` | Tạo Job TTS, polling trạng thái, phân quyền tải artifact | **PASSED** | ~0.60s |
| 6 | `tests/integration/test_migrations.py` | Nâng cấp DB trắng qua Alembic migration | **PASSED** | ~0.12s |
| 7 | `tests/integration/test_migrations.py` | Nâng cấp DB có sẵn dữ liệu bảo toàn 100% dữ liệu | **PASSED** | ~0.10s |
| 8 | `tests/integration/test_migrations.py` | Thực thi ràng buộc Khóa ngoại (Foreign Keys) SQLite | **PASSED** | ~0.08s |
| 9 | `tests/integration/test_migrations.py` | Kích hoạt chế độ ghi nhật ký SQLite WAL Mode | **PASSED** | ~0.09s |
| 10 | `tests/integration/test_security_hardened.py` | Ngăn chặn tấn công đua (Race Condition) trong onboarding | **PASSED** | ~0.18s |
| 11 | `tests/integration/test_security_hardened.py` | Hết hạn TTL của One-Time Bootstrap Token | **PASSED** | ~0.15s |
| 12 | `tests/integration/test_security_hardened.py` | Phân quyền RBAC & cô lập đa người dùng (403 Forbidden) | **PASSED** | ~0.22s |
| 13 | `tests/integration/test_spa_serving.py` | Phục vụ static SPA index.html và assets Vite qua FastAPI | **PASSED** | ~0.08s |
| 14 | `tests/integration/test_supervisor_resilience.py` | Tự động cô lập sự cố sập worker & khởi động lại trong suốt | **PASSED** | ~1.50s |

**Tổng kết:** 14/14 passed (100%), thời gian thực thi: **9.61s**.

---

## 4. KẾT LUẬN VÀ KIẾN NGHỊ

Hệ thống đã hoàn tất toàn diện các yêu cầu điều chỉnh kỹ thuật của bản rà soát Phase 1. Các khiếm khuyết về bảo mật token, thiếu hụt công cụ di chuyển database, nguy cơ rò rỉ tiến trình trên Windows, và sự thiếu hụt bằng chứng kiểm thử trình duyệt thực tế đều đã được khắc phục triệt để.

**Khuyến nghị:** Phê duyệt chuyển trạng thái Phase 1 thành **PASS** và sẵn sàng mở Gate PH1B để tiến hành chuẩn bị cho Giai đoạn Phase 1B (Benchmark & Spikes).
