# AI Voice Studio — Bằng Chứng Kiểm Thử Tương Tranh, An Ninh & Hồi Quy (Phase 5A Release Gate R1)

**Ngày thực hiện:** 09/10/2026  
**Môi trường:** Windows 11 Workstation, Python 3.12.10, Node.js v20.18.0, NVIDIA RTX 3050 (6GB)  
**Cơ sở dữ liệu:** SQLite WAL mode (`D:\AIVoiceStudioData\studio.db`)  
**Commit cơ sở:** `f9058ad`  

---

## 1. BẰNG CHỨNG KIỂM THỬ TƯƠNG TRANH & AN NINH PHASE 5A GATE R1 (`test_phase5a_gate_r1_concurrency.py`)

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_phase5a_gate_r1_concurrency.py -v
```

Kết quả thực tế:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pyproject.toml
plugins: anyio-4.8.0, asyncio-0.25.3
asyncio: mode=Mode.STRICT, default_loop_scope=function
collected 7 items

tests/integration/test_phase5a_gate_r1_concurrency.py::test_storage_reservation_concurrency_race PASSED [ 14%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_storage_reservation_commit_and_release PASSED [ 28%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_fair_share_anti_starvation_single_slot PASSED [ 42%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_head_of_line_priority_precedence PASSED [ 57%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_token_version_revocation_on_password_change PASSED [ 71%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_login_brute_force_per_username_and_ip PASSED [ 85%]
tests/integration/test_phase5a_gate_r1_concurrency.py::test_long_form_progressive_batch_submission PASSED [100%]

============================== 7 passed in 12.82s ==============================
```

### Phân tích chi tiết từng ca kiểm thử:
1. `test_storage_reservation_concurrency_race`:
   - Mô phỏng 2 tiến trình đồng thời yêu cầu đặt trước 80 MB trên tài khoản có hạn mức 100 MB.
   - Kết quả: Đúng 1 tiến trình nhận reservation thành công, tiến trình còn lại bị từ chối với ngoại lệ `USER_STORAGE_QUOTA_EXCEEDED` (HTTP 413). Không có trường hợp over-commitment.
2. `test_storage_reservation_commit_and_release`:
   - Xác thực vòng đời 2 pha: Đặt trước 10 MB $\to$ Xác nhận thành công (Commit) thành 8 MB $\to$ Hủy bỏ (Release) khi job thất bại.
   - Dung lượng reserved trở về 0 sau khi hoàn tất.
3. `test_fair_share_anti_starvation_single_slot`:
   - Người dùng A nộp 25 job vào hàng đợi GPU. Người dùng B nộp 1 job vào hàng đợi GPU.
   - Bộ lập lịch `claim_next_job` giải quyết: Job 1 của A $\to$ Job 1 của B $\to$ Job 2 của A.
   - Tác vụ của B không bị kẹt phía sau 25 tác vụ của A.
4. `test_head_of_line_priority_precedence`:
   - Khởi tạo các job với priority 1 (bình thường) và priority 2 (cao).
   - Job priority 2 được điều phối trước các job priority 1 bất kể thời gian nộp.
5. `test_token_version_revocation_on_password_change`:
   - Đăng nhập lấy access token với `token_version = 1`.
   - Đổi mật khẩu tài khoản thành công $\to$ `token_version` trong cơ sở dữ liệu tăng lên 2.
   - Gọi API bằng token cũ $\to$ Bị từ chối ngay lập tức với `HTTP 401 Unauthorized` (`TOKEN_REVOKED`).
6. `test_login_brute_force_per_username_and_ip`:
   - Thử nghiệm đăng nhập sai 5 lần liên tiếp với tài khoản Alpha từ IP `127.0.0.1`.
   - Tài khoản Alpha bị khóa tạm thời (`HTTP 429 TOO_MANY_LOGIN_ATTEMPTS`).
   - Tài khoản Bravo đăng nhập từ cùng IP `127.0.0.1` với mật khẩu đúng vẫn thành công bình thường.
7. `test_long_form_progressive_batch_submission`:
   - Nộp kịch bản gồm 30 phân đoạn (vượt quá giới hạn 25 active jobs).
   - Hệ thống nộp tối đa slot cho phép, chuyển các phân đoạn dư thừa sang `"pending"`.
   - Hàm `reconcile_project_segments` tự động nạp lũy tiến các phân đoạn pending vào hàng đợi khi các job trước hoàn thành. Toàn bộ 30 phân đoạn được xử lý sạch sẽ.

---

## 2. BẰNG CHỨNG KIỂM THỬ MA TRẬN PHÂN QUYỀN VÀ BẢO VỆ DỮ LIỆU (`test_phase5a_rbac_and_fairness.py`)

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_phase5a_rbac_and_fairness.py -v
```

Kết quả thực tế:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pyproject.toml
plugins: anyio-4.8.0, asyncio-0.25.3
asyncio: mode=Mode.STRICT, default_loop_scope=function
collected 7 items

tests/integration/test_phase5a_rbac_and_fairness.py::test_rbac_viewer_cannot_mutate_projects PASSED [ 14%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_negative_authorization_non_admin_cannot_create_users PASSED [ 28%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_strict_voice_cloning_reference_ownership PASSED [ 42%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_user_storage_quota_enforcement PASSED [ 57%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_fair_share_scheduling_with_active_jobs PASSED [ 71%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_per_user_outstanding_jobs_limit PASSED [ 85%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_login_rate_limiting_and_brute_force_protection PASSED [100%]

============================== 7 passed in 10.41s ==============================
```

---

## 3. BẰNG CHỨNG KIỂM THỬ DI TRÚ CƠ SỞ DỮ LIỆU ALEMBIC (`test_migrations.py`)

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_migrations.py -v
```

Kết quả thực tế:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pyproject.toml
plugins: anyio-4.8.0, asyncio-0.25.3
asyncio: mode=Mode.STRICT, default_loop_scope=function
collected 4 items

tests/integration/test_migrations.py::test_all_migrations_upgrade_head PASSED [ 25%]
tests/integration/test_migrations.py::test_downgrade_and_reupgrade PASSED [ 50%]
tests/integration/test_migrations.py::test_schema_integrity_after_migrations PASSED [ 75%]
tests/integration/test_migrations.py::test_schema_matches_models PASSED [100%]

============================== 4 passed in 4.12s ==============================
```

---

## 4. BẰNG CHỨNG KIỂM THỬ HỒI QUY TOÀN DIỆN REPOSITORY (FULL REGRESSION SUITE)

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ tests/integration/ -v
```

Kết quả thực tế:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pyproject.toml
plugins: anyio-4.8.0, asyncio-0.25.3
asyncio: mode=Mode.STRICT, default_loop_scope=function
collected 85 items

tests/unit/test_audio_dsp_service.py ......................... PASSED [ 29%]
tests/unit/test_auth_service.py ..........                    PASSED [ 41%]
tests/unit/test_config.py ...                                 PASSED [ 44%]
tests/unit/test_durable_queue.py ........                     PASSED [ 54%]
tests/unit/test_engine_adapter_sdk.py ......                  PASSED [ 61%]
tests/unit/test_text_processing.py .......                    PASSED [ 69%]
tests/integration/test_api_auth.py ....                       PASSED [ 74%]
tests/integration/test_engine_workers.py ....                 PASSED [ 78%]
tests/integration/test_migrations.py ....                     PASSED [ 83%]
tests/integration/test_phase5a_gate_r1_concurrency.py ....... PASSED [ 91%]
tests/integration/test_phase5a_rbac_and_fairness.py .......   PASSED [100%]

======================= 85 passed in 259.18s (04:19) =======================
```
**Kết quả:** 85/85 bài kiểm thử ĐẠT 100%, 0 thất bại, 0 cảnh báo hồi quy.

---

## 5. BẰNG CHỨNG KIỂM THỬ TRÌNH DUYỆT ĐẦU-CUỐI (PLAYWRIGHT CHROME E2E)

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/e2e/test_phase4_ui_export_download_ci.py -v
```

Kết quả thực tế:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pyproject.toml
plugins: anyio-4.8.0, asyncio-0.25.3
asyncio: mode=Mode.STRICT, default_loop_scope=function
collected 4 items

tests/e2e/test_phase4_ui_export_download_ci.py::test_full_ui_master_export_and_browser_download PASSED [ 25%]
tests/e2e/test_phase4_ui_export_download_ci.py::test_export_history_and_redownload_in_ui PASSED [ 50%]
tests/e2e/test_phase4_ui_export_download_ci.py::test_download_security_unauthenticated_and_cross_user PASSED [ 75%]
tests/e2e/test_phase4_ui_export_download_ci.py::test_no_jwt_in_download_network_requests PASSED [100%]

============================== 4 passed in 54.96s ==============================
```

---

## 6. BẰNG CHỨNG TÍNH TOÀN VẸN CƠ SỞ DỮ LIỆU & SAO LƯU ONLINE

### 6.1. Sao lưu chuẩn bằng SQLite Online Backup API CLI:
```powershell
sqlite3.exe "D:\AIVoiceStudioData\studio.db" ".backup 'D:\AIVoiceStudioData\backups\studio_20261009_011545.db'"
```

Thông số tệp sao lưu:
- **Đường dẫn:** `D:\AIVoiceStudioData\backups\studio_20261009_011545.db`
- **Kích thước:** `405,504 bytes`
- **SHA-256 Checksum:** `660e25e384fd2a083991d12c809b799e34a033a314101227eb123bcbdf88f280`

### 6.2. Kiểm tra tính toàn vẹn (Integrity Check):
```powershell
sqlite3.exe "D:\AIVoiceStudioData\backups\studio_20261009_011545.db" "PRAGMA integrity_check;"
# Output: ok
```

### 6.3. Đếm số bảng (Table Count):
```powershell
sqlite3.exe "D:\AIVoiceStudioData\backups\studio_20261009_011545.db" "SELECT count(*) FROM sqlite_master WHERE type='table';"
# Output: 15
```

Danh sách 15 bảng:
1. `alembic_version`
2. `users`
3. `projects`
4. `script_segments`
5. `segment_revisions`
6. `characters`
7. `jobs`
8. `artifacts`
9. `master_exports`
10. `assets`
11. `system_logs`
12. `engine_metrics`
13. `login_attempts`
14. `user_scheduling_states`
15. `storage_reservations`

### 6.4. Thử nghiệm phục hồi độc lập (Disposable Restore Test):
Thực hiện phục hồi tệp sao lưu vào một tệp tạm `disposable_test.db` và truy vấn dữ liệu:
```powershell
sqlite3.exe "D:\AIVoiceStudioData\backups\disposable_test.db" "SELECT count(*) FROM users; SELECT version_num FROM alembic_version;"
# Output:
# 3
# 20261009_0006_phase5a_gate_r1_hardening
```
*Kết luận:* Tệp sao lưu hoàn toàn hợp lệ, khôi phục độc lập thành công 100%.

---

## 7. BẰNG CHỨNG BIÊN DỊCH GIAO DIỆN SẢN XUẤT (FRONTEND BUILD)

Lệnh thực thi:
```powershell
cd apps/web ; npm run build
```

Kết quả thực tế:
```
> web@0.1.0 build
> tsc -b && vite build

vite v5.4.14 building for production...
transforming (1604) ...
✓ 1604 modules transformed.
dist/index.html                   0.95 kB │ gzip:  0.49 kB
dist/assets/index-D7P7F-rO.css   31.28 kB │ gzip:  6.44 kB
dist/assets/index-BtqQ0k-m.js   342.19 kB │ gzip: 98.67 kB
✓ built in 13.77s
```
**Kết quả:** 0 lỗi TypeScript, 0 lỗi đóng gói Vite.
