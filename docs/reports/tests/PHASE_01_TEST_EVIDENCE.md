# AI VOICE STUDIO — BẰNG CHỨNG KIỂM THỬ GIAI ĐOẠN PHASE 1
**Ngày kiểm thử:** 2026-10-08  
**Môi trường:** Windows 10/11, Python 3.12.10, Node v24.14.1, pytest 9.1.1  
**Kết quả kiểm thử:** 6/6 PASSED (100% Thành công)  

---

## 1. TỔNG HỢP KẾT QUẢ TEST SUITE

Lệnh thực thi toàn bộ test suite:
```powershell
.venv\Scripts\pytest -v tests/
```

Kết quả đầu ra:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- D:\C\Dev\du an\TTS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 6 items

tests/contract/test_mock_engine.py::test_manifest_validation PASSED      [ 16%]
tests/contract/test_mock_engine.py::test_mock_worker_lifecycle_and_contract PASSED [ 33%]
tests/integration/test_auth_api.py::test_auth_onboarding_lifecycle PASSED [ 50%]
tests/integration/test_jobs_api.py::test_tts_job_lifecycle_and_artifact PASSED [ 66%]
tests/integration/test_spa_serving.py::test_spa_index_and_assets PASSED  [ 83%]
tests/integration/test_supervisor_resilience.py::test_worker_crash_isolation_and_restart PASSED [100%]

============================== 6 passed in 2.87s ==============================
```

---

## 2. CHI TIẾT TỪNG BÀI KIỂM THỬ

### 2.1. Kiểm thử hợp đồng SDK Manifest (`test_manifest_validation`)
- **Mục tiêu:** Xác thực cú pháp schema Pydantic v2 của `engine.manifest.json` thuộc Mock Engine.
- **Tiêu chí kiểm tra:**
  - `engine_id == "mock-tts"`
  - Khai báo đúng `capabilities`: `text_to_speech`, `speaker_selection`.
  - Khai báo đúng `supported_languages`: `["vi", "zh", "en"]`.
  - Giá trị `default_sample_rate == 44100`.
- **Kết quả:** PASSED.

### 2.2. Vòng đời Worker & Giao thức SDK (`test_mock_worker_lifecycle_and_contract`)
- **Mục tiêu:** Kiểm tra khởi động tiến trình worker độc lập qua tham số `--port 0` (cổng động HĐH cấp) và xác thực header `X-Worker-Token`.
- **Tiêu chí kiểm tra:**
  - Client không có token bị từ chối với lỗi 401.
  - Client có token lấy được thông tin `/health` (`status: healthy`, `device: cpu`).
  - Lấy danh sách preset voices qua `/info`.
  - Gửi yêu cầu `/synthesize` nhận về mảng byte âm thanh WAV 16-bit Mono hợp lệ.
  - Gửi ngôn ngữ không hỗ trợ nhận về chuẩn lỗi RFC 9457 mã 422 (`UNSUPPORTED_LANGUAGE`).
  - Gọi `/unload` giải phóng tài nguyên thành công.
- **Kết quả:** PASSED.

### 2.3. Quy trình Onboarding & Bảo mật JWT (`test_auth_onboarding_lifecycle`)
- **Mục tiêu:** Xác thực quy trình Zero-Trust Localhost khi khởi tạo hệ thống lần đầu.
- **Tiêu chí kiểm tra:**
  - Trạng thái ban đầu: `needs_onboarding: true`, `total_users: 0`.
  - Thử dùng token sai -> 401 `INVALID_SETUP_TOKEN`.
  - Dùng token hợp lệ -> tạo tài khoản admin, mã băm Argon2id, nhận JWT Bearer token (HTTP 201).
  - Trạng thái sau khởi tạo: `needs_onboarding: false`, `total_users: 1`.
  - Cố tình gọi bootstrap lần 2 -> 409 Conflict `ALREADY_INITIALIZED`.
  - Đăng nhập với mật khẩu sai -> 401 `INVALID_CREDENTIALS`.
  - Đăng nhập đúng mật khẩu -> 200 kèm JWT token mới.
  - Gọi `/api/v1/auth/me` với Bearer token trả về hồ sơ admin.
  - Gọi `/api/v1/auth/me` không có token -> 401 `UNAUTHORIZED`.
- **Kết quả:** PASSED.

### 2.4. Vòng đời Job & Quản lý Audio Artifact (`test_tts_job_lifecycle_and_artifact`)
- **Mục tiêu:** Kiểm tra toàn bộ luồng xử lý tổng hợp giọng nói từ lúc tạo job đến khi lấy file audio.
- **Tiêu chí kiểm tra:**
  - Gửi `POST /api/v1/jobs/speech` tạo job ở trạng thái `queued` (HTTP 201).
  - Tác vụ chạy nền phi đồng bộ cập nhật tiến độ (20% -> 50% -> 80% -> 100%) và chuyển thành `completed`.
  - Khóa Idempotency hoạt động: gửi lại cùng `idempotency_key` trả về bản ghi job cũ mà không tạo lại.
  - Lấy siêu dữ liệu `GET /api/v1/artifacts/{id}` trả về kích thước, thời lượng > 0s, sample rate 44.1kHz.
  - Tải file `GET /api/v1/artifacts/{id}/file` nhận về file WAV chuẩn bắt đầu bằng bytes `RIFF` và chứa `WAVE`.
  - Gửi ngôn ngữ không hỗ trợ trả về RFC 9457 `422 UNSUPPORTED_LANGUAGE`.
  - Gửi engine không tồn tại trả về RFC 9457 `400 ENGINE_NOT_FOUND`.
- **Kết quả:** PASSED.

### 2.5. Khả năng chịu lỗi & Phục hồi Worker (`test_worker_crash_isolation_and_restart`)
- **Mục tiêu:** Kiểm tra cơ chế cách ly lỗi (fault isolation) của Process Supervisor khi worker bị tắt đột ngột.
- **Tiêu chí kiểm tra:**
  - Khởi động worker bình thường (`is_alive() == True`).
  - Dùng lệnh `kill()` hủy đột ngột tiến trình worker (`is_alive() == False`).
  - Supervisor phát hiện tiến trình đã chết và trả về `client == None` (fail-safe).
  - Gọi khởi động lại, Supervisor tự động spawn lại tiến trình worker mới trên cổng loopback mới và kết nối lại thành công.
  - Máy chủ lõi FastAPI không bị gián đoạn hay đổ sập.
- **Kết quả:** PASSED.

### 2.6. Phục vụ Giao diện SPA (`test_spa_index_and_assets`)
- **Mục tiêu:** Xác thực FastAPI mount và phân phối bundle SPA tĩnh thành công.
- **Tiêu chí kiểm tra:**
  - Truy cập `/` trả về mã 200 kèm nội dung HTML chứa tiêu đề ứng dụng.
  - Truy cập đường dẫn định tuyến phía client bất kỳ (ví dụ `/dashboard/speech-studio`) được chuyển hướng (fallback) về `index.html` của SPA với mã 200.
- **Kết quả:** PASSED.

---

## 3. BẰNG CHỨNG KIỂM TRA KHỞI ĐỘNG SMOKE TEST MÁY CHỦ THỰC TẾ

```text
=================================================================
 [AI VOICE STUDIO] FIRST-RUN ONBOARDING REQUIRED
 One-Time Local Bootstrap Token: d7118bfaba011ce5577f24b01753a35f6e633d3cad51e3cb
 Web UI: http://127.0.0.1:8765
=================================================================

Health check: 200 {'status': 'ok', 'version': '1.0.0', 'database': 'healthy', 'timestamp': '2026-10-08T03:03:49.265362+00:00'}
Auth status: 200 {'needs_onboarding': True, 'total_users': 0}
SPA Root: 200 text/html; charset=utf-8

Shutting down AI Voice Studio worker processes...
Server cleanly shutdown.
```
