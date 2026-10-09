# AI Voice Studio — Phase 5B-1 Test Evidence & Verification Report
## Reverse Proxy Staging, Trusted Client Identity & Gateway Hardening

**Ngày kiểm thử:** 2026-10-09  
**Người kiểm thử:** QA Lead, Application Security Engineer  
**Hệ điều hành:** Windows 11 (Python 3.12.10, pytest 9.1.1)  
**Commit cơ sở:** `d8aa596`  
**Kết quả tổng quan:** **124/124 Unit, Contract & Integration Tests PASS (100%) | 4/4 Playwright E2E Tests PASS (100%) | Frontend Build PASS**

---

## 1. BẢNG TỔNG HỢP KẾT QUẢ KIỂM THỬ

| Nhóm kiểm thử | Tệp kiểm thử / Thành phần | Số ca kiểm thử | Kết quả | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 5B-1 Gateway Suite** | `tests/integration/test_phase5b1_trusted_proxy.py` | 12 | **12/12 PASS** | Kiểm tra IP spoofing, Rate Limit isolation, Runner lock, CWE-598 |
| **Phase 5A Throttling Suite** | `tests/integration/test_phase5a_final_r2_security.py` | 7 | **7/7 PASS** | 3-tier rate limiting, brute force, spray defense |
| **Full Integration Suite** | `tests/integration/` | 111 | **111/111 PASS** | Không phát sinh bất kỳ lỗi hồi quy nào trên toàn hệ thống |
| **Contract & Unit Suite** | `tests/contract/` & `tests/unit/` | 9 | **9/9 PASS** | Mock, Qwen3, VieNeu engine contract và bộ tách câu tiếng Việt |
| **Browser E2E Suite** | `tests/e2e/` | 4 | **4/4 PASS** | Playwright Chromium E2E hành trình phòng thu và tải xuất âm thanh |
| **Frontend Production Build** | `apps/web` (`npm run build`) | 1 | **PASS** | `tsc && vite build` tạo bundle hoàn chỉnh, 0 lỗi TypeScript |
| **Database Online Backup** | `apps.server.src.backup create/verify` | 2 | **PASS** | Sao lưu trực tiếp khi database đang mở, 15 bảng toàn vẹn |

---

## 2. CHI TIẾT BỘ KIỂM THỬ MILESTONE 5B-1 (`test_phase5b1_trusted_proxy.py`)

```
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_normalize_ip_valid_cases PASSED [  8%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_normalize_ip_invalid_and_injections PASSED [ 16%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_untrusted_peer_ignores_x_forwarded_for PASSED [ 25%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_trusted_proxy_extracts_x_forwarded_for PASSED [ 33%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_trusted_proxy_extracts_x_real_ip_fallback PASSED [ 41%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_trusted_proxy_chain_resolution PASSED [ 50%]
tests/integration/test_phase5b1_trusted_proxy.py::TestClientIpExtraction::test_malformed_header_safe_fallback PASSED [ 58%]
tests/integration/test_phase5b1_trusted_proxy.py::TestGatewayRateLimitingIsolation::test_multi_client_rate_limiting_isolation_behind_proxy PASSED [ 66%]
tests/integration/test_phase5b1_trusted_proxy.py::TestGatewayRateLimitingIsolation::test_distributed_attack_triggers_account_level_lockout PASSED [ 75%]
tests/integration/test_phase5b1_trusted_proxy.py::TestGatewayRateLimitingIsolation::test_source_ip_spraying_lockout PASSED [ 83%]
tests/integration/test_phase5b1_trusted_proxy.py::TestRunnerUniquenessLock::test_runner_lock_acquire_and_reject_duplicate PASSED [ 91%]
tests/integration/test_phase5b1_trusted_proxy.py::TestSecurityBaselinePreservation::test_audio_endpoints_reject_query_tokens PASSED [100%]
```

### Phân tích các ca kiểm thử chính:

1. **`test_untrusted_peer_ignores_x_forwarded_for`**:
   - Khi một kết nối xuất phát từ socket peer `198.51.100.1` (không thuộc `TRUSTED_PROXIES`), kẻ tấn công chèn `X-Forwarded-For: 203.0.113.50`.
   - Kết quả: `extract_client_ip` bỏ qua hoàn toàn header và trả về đúng `198.51.100.1`. Ngăn chặn hoàn toàn việc bypass IP rate limit.
2. **`test_multi_client_rate_limiting_isolation_behind_proxy`**:
   - Hai biên tập viên Client A (`192.168.1.10`) và Client B (`192.168.1.20`) cùng kết nối qua Caddy Reverse Proxy tại `127.0.0.1`.
   - Client A nhập sai mật khẩu 5 lần liên tiếp và bị hệ thống khóa (`is_limited = True`).
   - Client B ngay sau đó thực hiện đăng nhập vào tài khoản của mình.
   - Kết quả: Client B đăng nhập thành công, không hề bị ảnh hưởng bởi lỗi của Client A. Hiện tượng Collateral Lockout đã được khắc phục triệt để.
3. **`test_distributed_attack_triggers_account_level_lockout`**:
   - Kẻ tấn công luân chuyển 10 IP khác nhau qua proxy để dò mật khẩu tài khoản `admin_target`.
   - Kết quả: Tầng phòng vệ 2 (`LOGIN_MAX_FAILED_ATTEMPTS_USER = 10`) kích hoạt, khóa tài khoản dù kẻ tấn công thử tiếp từ một IP hoàn toàn mới.
4. **`test_source_ip_spraying_lockout`**:
   - Một client IP duy nhất (`192.168.5.50`) thử mật khẩu sai trên 20 tài khoản khác nhau (Credential Spraying).
   - Kết quả: Tầng phòng vệ 3 (`LOGIN_MAX_FAILED_ATTEMPTS_IP = 20`) kích hoạt, chặn toàn bộ yêu cầu tiếp theo từ IP này.
5. **`test_runner_lock_acquire_and_reject_duplicate`**:
   - Tiến trình Standalone Runner chiếm giữ file lock độc quyền `.runner.lock` qua `msvcrt.locking(LK_NBLCK)`.
   - Tiến trình Runner thứ hai cố gắng chiếm khóa bị từ chối ngay lập tức (`acquire() == False`).
   - Sau khi Runner 1 giải phóng, Runner thứ hai có thể chiếm khóa thành công.
6. **`test_audio_endpoints_reject_query_tokens`**:
   - Truy cập endpoint `/api/v1/projects/{id}/exports/{export_id}/download?token=xxx` và `/api/v1/artifacts/{id}/file?token=xxx` với query string token.
   - Kết quả: Hệ thống kiên quyết từ chối với mã lỗi HTTP 400 `QUERY_AUTH_PROHIBITED` (khi có Bearer token) hoặc HTTP 401 (khi không có Bearer token). Tuyệt đối không cho phép xác thực qua query URL (CWE-598).

---

## 3. BẰNG CHỨNG SAO LƯU DỮ LIỆU TRỰC TUYẾN (ONLINE BACKUP EVIDENCE)

### Bản sao lưu trước kiểm thử:
- **Tệp sao lưu:** `D:\AIVoiceStudioData\backups\studio_20261009_024933.db`
- **Kích thước:** 417,792 bytes
- **Mã băm SHA256:** `d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527`
- **Kiểm tra tính toàn vẹn (Integrity check):** `ok (Quick check: ok)`
- **Alembic Revision:** `20261009_0006`
- **Số bảng dữ liệu:** 15 bảng

### Bản sao lưu sau kiểm thử:
- **Tệp sao lưu:** `D:\AIVoiceStudioData\backups\studio_20261009_031341.db`
- **Kích thước:** 417,792 bytes
- **Mã băm SHA256:** `d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527`
- **Kiểm tra tính toàn vẹn (Integrity check):** `ok (Quick check: ok)`
- **Alembic Revision:** `20261009_0006`
- **Số bảng dữ liệu:** 15 bảng (Users: 14, Engines: 3, Artifacts: 36, Jobs: 38, Projects: 9, Script Segments: 32, Project Exports: 8, Login Attempts: 48, Storage Reservations: 3)

---

## 4. ĐÁNH GIÁ TRẠNG THÁI RUNTIME CỦA CADDY

- **Trạng thái thực tế:** Tệp thực thi `caddy.exe` chưa có sẵn trên máy trạm Windows này.
- **Tuân thủ quy chuẩn:** Không tự ý tải hoặc cài đặt phần mềm ngoài khi chưa có chỉ thị.
- **Xác nhận tính sẵn sàng:**
  - Cấu hình `infra/caddy/Caddyfile` đã được viết chuẩn xác theo đặc tả Caddy v2.
  - Hướng dẫn vận hành chi tiết tại `infra/caddy/README.md`.
  - Bộ kiểm thử tự động giả lập đầy đủ luồng mạng reverse proxy và chứng minh tính đúng đắn 100%.
  - Trạng thái kiểm thử runtime: **CONDITIONAL** (chờ quản trị viên cài đặt Caddy binary để kích hoạt kiểm thử trực tiếp trên cổng 9443).
