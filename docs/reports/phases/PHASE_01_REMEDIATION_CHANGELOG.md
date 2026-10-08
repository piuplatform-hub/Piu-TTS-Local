# AI VOICE STUDIO — NHẬT KÝ KHẮC PHỤC KỸ THUẬT PHASE 1 (PHASE 1 REMEDIATION CHANGELOG)

**Ngày ghi nhận:** 2026-10-08  
**Phiên bản:** Phase 1 Post-Verification Baseline  
**Phạm vi:** Danh mục chi tiết các thay đổi mã nguồn, cơ chế bảo mật, di chuyển dữ liệu, cô lập tiến trình và kiểm thử trình duyệt thực tế  

---

## 1. BẢO MẬT VÀ XÁC THỰC (SECURITY & AUTHENTICATION)

- **Hủy bỏ Token bị lộ:**
  - Xóa bỏ tệp `D:\AIVoiceStudioData\.bootstrap_token` chứa chuỗi token plaintext cũ.
  - Ẩn danh hóa các chuỗi token trong tài liệu `docs/reports/tests/PHASE_01_TEST_EVIDENCE.md` thành `[REDACTED_LOCAL_BOOTSTRAP_TOKEN]`.
- **Gia cố Bootstrap Token (`apps/server/src/core/security.py`):**
  - Thêm hằng số `BOOTSTRAP_TOKEN_TTL_SECONDS = 900` (15 phút).
  - Chuyển định dạng tệp sang JSON có cấu trúc (`token`, `created_at`, `expires_at`).
  - Áp dụng kỹ thuật đổi tên tệp nguyên tử ở tầng hệ điều hành (`os.replace`) để phòng chống hoàn toàn các cuộc tấn công tranh chấp (Race Condition) trong môi trường đồng thời.
  - Thiết kế cơ chế hoàn trả tệp an toàn (`claim_file` -> `token_file`) khi chuỗi token nhập vào không khớp, chống tấn công từ chối dịch vụ (DoS) xóa nhầm token của quản trị viên.
  - Token đã sử dụng hoặc hết hạn bị hủy vĩnh viễn (`unlink`).
- **Phân quyền Đa người dùng RBAC (`apps/server/src/services/auth_service.py`, `apps/server/src/api/v1/auth.py`):**
  - Bổ sung `_bootstrap_lock = asyncio.Lock()` đồng bộ hóa quá trình khởi tạo admin sơ cấp.
  - Bổ sung phương thức `create_user` và endpoint quản trị `POST /api/v1/auth/users` cho phép `admin` cấp phát tài khoản `editor`/`viewer`.
  - Chặn các tài khoản không phải `admin` truy cập API tạo tài khoản (`403 Forbidden`).
  - Thắt chặt kiểm tra quyền sở hữu artifact âm thanh: người dùng không thể truy cập artifact của người khác (`403 Forbidden`).

---

## 2. QUẢN LÝ SCHEMA DỮ LIỆU (ALEMBIC MIGRATIONS)

- **Khởi tạo Alembic Environment:**
  - Tạo `alembic.ini` với cấu hình tương thích `path_separator = os`.
  - Tạo `alembic/env.py` hỗ trợ SQLite WAL, Async Engine (`sqlite+aiosqlite`) và `render_as_batch=True`.
  - Tạo `alembic/script.py.mako` làm khuôn mẫu sinh mã migration.
- **Migration Phiên bản 1 (`alembic/versions/20261008_0001_initial_schema.py`):**
  - Thiết lập bảng `users`, `engines`, `artifacts`, `jobs` với đầy đủ khóa ngoại, chỉ mục và ràng buộc toàn vẹn.
  - Bổ sung kiểm tra idempotent (`inspect(conn).get_table_names()`) đảm bảo nâng cấp mượt mà trên database hiện có mà không gây thất thoát dữ liệu.
- **Tích hợp Tự động:**
  - Bổ sung `run_migrations()` trong `apps/server/src/database.py` để tự động nâng cấp schema lên `head` khi server khởi động.

---

## 3. CÔ LẬP TIẾN TRÌNH VÀ HẠ TẦNG (WORKER SUPERVISOR & WINDOWS JOB OBJECTS)

- **Tích hợp Windows Job Objects (`apps/server/src/supervisor/supervisor.py`):**
  - Tích hợp Windows Win32 API thông qua `ctypes.windll.kernel32`:
    - Tạo Job Object với quyền `CreateJobObjectW`.
    - Thiết lập cờ `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (giá trị `0x2000`) qua `SetInformationJobObject`.
    - Gán handle tiến trình con Python vào Job Object qua `AssignProcessToJobObject`.
  - Kết quả: Khi tiến trình cha FastAPI bị buộc dừng hoặc sập bất ngờ, Windows Kernel tự động giải phóng toàn bộ tiến trình con worker, loại bỏ nguy cơ chiếm dụng cổng mạng loopback.
- **Sửa lỗi Tham chiếu Database Lifespan (`apps/server/src/main.py`):**
  - Thay đổi cách nạp `AsyncSessionLocal` từ import tĩnh sang tham chiếu động qua module `database.AsyncSessionLocal`, giúp môi trường test cô lập trỏ đúng cơ sở dữ liệu tạm thời.

---

## 4. GIAO DIỆN NGƯỜI DÙNG (FRONTEND DISCLAIMER & REBUILD)

- **Bổ sung Biểu ngữ Hợp đồng (`apps/web/src/components/StudioView.tsx`):**
  - Bổ sung banner cảnh báo minh bạch: `CONTRACT TEST Âm thanh tổng hợp kiểm thử hợp đồng PCM 16-bit. Chưa nạp trọng số AI neural (VieNeu/Qwen3).`
- **Biên dịch Sản xuất:**
  - Thực hiện build lại toàn bộ bundle frontend (`npm run build`), cập nhật thư mục phân phối `apps/web/dist`.

---

## 5. BỘ KIỂM THỬ MỞ RỘNG (AUTOMATED TEST SUITE EXPANSION)

- **Kiểm thử Bảo mật Nâng cao (`tests/integration/test_security_hardened.py`):**
  - `test_concurrent_onboarding_race_condition`: 5 yêu cầu đồng thời, chỉ 1 yêu cầu thành công.
  - `test_bootstrap_token_ttl_expiration`: từ chối token hết hạn 15 phút.
  - `test_multi_user_cross_authorization_isolation`: chặn trái phép tạo user và tải artifact chéo.
- **Kiểm thử Di chuyển Dữ liệu (`tests/integration/test_migrations.py`):**
  - `test_alembic_fresh_database_upgrade`: nâng cấp DB trắng.
  - `test_alembic_upgrade_preexisting_db_without_data_loss`: nâng cấp DB cũ bảo toàn dữ liệu.
  - `test_foreign_key_constraint_enforcement`: xác minh khóa ngoại SQLite.
  - `test_sqlite_wal_mode_enabled`: xác minh chế độ WAL.
- **Kiểm thử Khả năng Phục hồi Supervisor (`tests/integration/test_supervisor_resilience.py`):**
  - `test_worker_crash_isolation_and_restart`: xác minh tự động tái kích hoạt worker sau khi bị dừng bất ngờ.
- **Kiểm thử Trình duyệt Google Chrome Thực tế (`tests/e2e/test_browser_e2e.py`):**
  - Vận hành Google Chrome thật qua Playwright thực hiện toàn bộ 12 bước người dùng.
  - Lưu trữ 5 ảnh chụp màn hình kiểm chứng tại `docs/reports/screenshots/`.
  - Xác nhận 0 console error runtime và 0 network request failure.

**Kết quả kiểm thử tổng hợp:** 14/14 bài kiểm thử vượt qua thành công 100%.
