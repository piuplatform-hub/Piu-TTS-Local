# AI VOICE STUDIO — BẰNG CHỨNG KIỂM THỬ GIAI ĐOẠN PHASE 1 (CẬP NHẬT HẬU KIỂM TOÁN)

**Ngày kiểm thử:** 2026-10-08  
**Môi trường:** Windows 10/11, Python 3.12.10, Node v24.14.1, pytest 9.1.1, Playwright 1.63.0, Google Chrome 142.x  
**Kết quả kiểm thử:** **14/14 PASSED (100% Thành công)**  

---

## 1. TỔNG HỢP KẾT QUẢ TEST SUITE

Lệnh thực thi toàn bộ test suite:
```powershell
.venv\Scripts\pytest -v tests/
```

Kết quả đầu ra thực tế:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- D:\C\Dev\du an\TTS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 14 items

tests/contract/test_mock_engine.py::test_manifest_validation PASSED      [  7%]
tests/contract/test_mock_engine.py::test_mock_worker_lifecycle_and_contract PASSED [ 14%]
tests/e2e/test_browser_e2e.py::test_real_browser_end_to_end_journey PASSED [ 21%]
tests/integration/test_auth_api.py::test_auth_onboarding_lifecycle PASSED [ 28%]
tests/integration/test_jobs_api.py::test_tts_job_lifecycle_and_artifact PASSED [ 35%]
tests/integration/test_migrations.py::test_alembic_fresh_database_upgrade PASSED [ 42%]
tests/integration/test_migrations.py::test_alembic_upgrade_preexisting_db_without_data_loss PASSED [ 50%]
tests/integration/test_migrations.py::test_foreign_key_constraint_enforcement PASSED [ 57%]
tests/integration/test_migrations.py::test_sqlite_wal_mode_enabled PASSED [ 64%]
tests/integration/test_security_hardened.py::test_concurrent_onboarding_race_condition PASSED [ 71%]
tests/integration/test_security_hardened.py::test_bootstrap_token_ttl_expiration PASSED [ 78%]
tests/integration/test_security_hardened.py::test_multi_user_cross_authorization_isolation PASSED [ 85%]
tests/integration/test_spa_serving.py::test_spa_index_and_assets PASSED  [ 92%]
tests/integration/test_supervisor_resilience.py::test_worker_crash_isolation_and_restart PASSED [100%]

============================= 14 passed in 9.61s ==============================
```

---

## 2. CHI TIẾT TỪNG PHÂN HỆ KIỂM THỬ

### 2.1. Hợp đồng SDK & Mock Engine (`tests/contract/`)
- `test_manifest_validation`: Kiểm định cấu trúc `engine.manifest.json` theo schema Pydantic v2. Khai báo đúng `capabilities`, `supported_languages: ["vi", "zh", "en"]`, thiết bị `cpu`.
- `test_mock_worker_lifecycle_and_contract`: Kiểm tra khởi động tiến trình worker độc lập qua tham số `--port 0` (cổng động HĐH cấp) và xác thực header `X-Worker-Token`. Sinh âm thanh WAV hợp lệ chuẩn PCM 16-bit 44.1kHz.

### 2.2. Kiểm thử Trình duyệt Google Chrome Thực tế E2E (`tests/e2e/test_browser_e2e.py`)
- Khởi chạy Google Chrome thực tế trên Windows thông qua Playwright.
- Thực hiện đầy đủ hành trình 12 bước: Onboarding với bootstrap token -> Đăng nhập -> Chọn Engine -> Nhập văn bản tiếng Việt -> Tạo giọng nói -> Polling thanh tiến độ 100% -> Kiểm tra Audio Player -> Tải file WAV -> Xem lịch sử tác vụ -> Đăng xuất bảo vệ.
- Lưu trữ 5 ảnh chụp màn hình minh chứng tại `docs/reports/screenshots/`.
- Xác nhận 0 console error runtime và 0 network request failure.

### 2.3. Cơ sở dữ liệu & Di chuyển Schema Alembic (`tests/integration/test_migrations.py`)
- `test_alembic_fresh_database_upgrade`: Kiểm tra nâng cấp cơ sở dữ liệu rỗng lên schema mới nhất (`head`) thông qua script Alembic.
- `test_alembic_upgrade_preexisting_db_without_data_loss`: Kiểm tra nâng cấp idempotent trên database đã có dữ liệu mà không làm mất bản ghi cũ.
- `test_foreign_key_constraint_enforcement`: Xác minh SQLite thực thi nghiêm ngặt ràng buộc khóa ngoại `PRAGMA foreign_keys=ON`.
- `test_sqlite_wal_mode_enabled`: Xác minh SQLite hoạt động ở chế độ `PRAGMA journal_mode=WAL`.

### 2.4. An toàn Bảo mật & RBAC (`tests/integration/test_security_hardened.py`, `test_auth_api.py`)
- `test_concurrent_onboarding_race_condition`: Gửi 5 yêu cầu bootstrap đồng thời; cơ chế atomic file rename ở tầng OS đảm bảo chỉ 1 yêu cầu duy nhất thành công, loại bỏ hoàn toàn tranh chấp race condition.
- `test_bootstrap_token_ttl_expiration`: Kiểm tra thời hạn sống 15 phút (TTL) của token; token quá hạn bị từ chối 401 Unauthorized.
- `test_multi_user_cross_authorization_isolation`: Kiểm tra phân quyền RBAC; người dùng role `editor` không thể tạo người dùng mới và không thể truy cập artifact âm thanh của người khác (nhận mã 403 Forbidden).
- `test_auth_onboarding_lifecycle`: Kiểm tra vòng đời onboarding, băm mật khẩu Argon2id, cấp phát JWT và chặn đăng ký lặp lại (409 Conflict).

### 2.5. Phục vụ Ứng dụng & Độ Ổn định Supervisor (`tests/integration/`)
- `test_tts_job_lifecycle_and_artifact`: Kiểm tra tạo Job, xử lý worker ngầm, tạo artifact và cấp phép tải file WAV.
- `test_spa_index_and_assets`: Kiểm tra máy chủ FastAPI phục vụ tĩnh toàn bộ bundle React/Vite (`index.html`, JavaScript, CSS).
- `test_worker_crash_isolation_and_restart`: Giả lập sập worker con đột ngột; Supervisor phát hiện và tự động khởi tạo lại trong suốt với cờ Windows Job Object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
