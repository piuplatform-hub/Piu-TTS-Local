# AI VOICE STUDIO — BÁO CÁO ĐÁNH GIÁ PHASE 5B-1 FINAL RUNTIME READINESS
## KIỂM TRA SẴN SÀNG KHỞI CHẠY RUNTIME, KIỂM TOÁN DỮ LIỆU & BẢO VỆ API STARTUP

- **Dự án**: AI Voice Studio
- **Kiến trúc**: R1.1 (FastAPI Backend + Vite/React Frontend + Kokoro/Qwen3/VieNeu Engines)
- **Giai đoạn**: Phase 5B-1 Final Runtime Readiness — Rà soát Khởi động API, Dữ liệu Thử nghiệm & Kiểm thử Hợp đồng
- **Ngày thực hiện**: 2026-10-09
- **Người thực hiện**: Principal Infrastructure Architect, Application Security Engineer, Windows Deployment Engineer, QA Lead
- **Commit cơ sở**: `3b47cac`
- **Trạng thái Gate**: **CONDITIONAL PASS** (Logic bảo mật, Khởi động API, Dữ liệu & Hợp đồng: **PASS**; Caddy Runtime: **BLOCKED**)

---

## 1. TỔNG QUAN VÀ TRẠNG THÁI GATE

Giai đoạn **Phase 5B-1** chỉ cho phép thiết lập và thử nghiệm cổng biên ngược trên giao diện loopback cục bộ (`127.0.0.1`, cổng `9443`). Mọi kết nối ra ngoài LAN (`0.0.0.0`), thay đổi Windows Firewall hoặc cài đặt root certificate vào hệ điều hành đều **bị nghiêm cấm tuyệt đối**.

Báo cáo này hoàn tất 4 mục tiêu kỹ thuật cốt lõi:
1. Rà soát và khóa chặt toàn bộ các lối khởi động Uvicorn, loại bỏ hoàn toàn khả năng vô tình kích hoạt lại `ProxyHeadersMiddleware`.
2. Kiểm toán và làm sạch an toàn các bản ghi thử nghiệm thủ công phát sinh ngoài ý muốn trong cơ sở dữ liệu chính `studio.db`, có sao lưu dự phòng.
3. Chạy kiểm thử hồi quy các bộ test hợp đồng engine (`tests/contract`), build production giao diện frontend (`apps/web: npm run build`) và kiểm chứng phục vụ tệp tĩnh SPA.
4. Xác minh tình trạng tệp nhị phân `caddy.exe` và cung cấp quy trình vận hành chi tiết cho Product Owner phê duyệt.

---

## 2. RÀ SOÁT VÀ KHÓA CHẶT API STARTUP (UVICORN)

### 2.1. Phân tích Các Lối Khởi chạy Uvicorn
Một lỗ hổng tiềm tàng của Uvicorn là khi được gọi từ giao diện dòng lệnh (CLI) mặc định (`python -m uvicorn ...`), Uvicorn tự động kích hoạt `proxy_headers=True` và `forwarded_allow_ips="127.0.0.1,::1"`. Điều này sẽ âm thầm chèn `ProxyHeadersMiddleware` vào trước ứng dụng FastAPI và ghi đè `scope["client"]` bằng `X-Forwarded-For`.

### 2.2. Các Biện pháp Đã Triển khai
1. **Chuẩn hóa Module Entrypoint (`apps/server/src/__main__.py`)**:
   Đã tạo mới tệp [apps/server/src/__main__.py](file:///d:/C/Dev/du%20an/TTS/apps/server/src/__main__.py) để khi lập trình viên hoặc kịch bản vận hành thực thi:
   ```powershell
   .venv\Scripts\python.exe -m apps.server.src
   # hoặc:
   .venv\Scripts\python.exe -m apps.server.src.main
   ```
   Hệ thống sẽ luôn tự động áp dụng:
   ```python
   proxy_headers = settings.UVICORN_PROXY_HEADERS  # Luôn là False
   forwarded_allow_ips = settings.UVICORN_FORWARDED_ALLOW_IPS  # Luôn là ""
   ```
2. **Khóa Chặt Tất cả Bộ Kiểm thử E2E Trình duyệt**:
   Các tệp kiểm thử tự động khởi động server nền Uvicorn đã được cập nhật đồng bộ để truyền tường minh các cờ an ninh:
   - [tests/e2e/test_browser_e2e.py](file:///d:/C/Dev/du%20an/TTS/tests/e2e/test_browser_e2e.py)
   - [tests/e2e/test_phase3_browser_e2e.py](file:///d:/C/Dev/du%20an/TTS/tests/e2e/test_phase3_browser_e2e.py)
   - [tests/e2e/test_phase4_browser_e2e.py](file:///d:/C/Dev/du%20an/TTS/tests/e2e/test_phase4_browser_e2e.py)
   - [tests/e2e/test_phase4_ui_export_download_ci.py](file:///d:/C/Dev/du%20an/TTS/tests/e2e/test_phase4_ui_export_download_ci.py)
3. **Cập nhật Tài liệu Vận hành**:
   Trong [infra/caddy/README.md](file:///d:/C/Dev/du%20an/TTS/infra/caddy/README.md), lệnh khởi chạy backend đã được chuẩn hóa với cờ `--no-proxy-headers --forwarded-allow-ips ""`.

---

## 3. KIỂM TOÁN VÀ DỌN DẸP DỮ LIỆU THỬ NGHIỆM THỦ CÔNG

### 3.1. Bằng chứng Dữ liệu Thử nghiệm Trong Cơ sở Dữ liệu Chính
Khi thực hiện kiểm toán cơ sở dữ liệu chính tại `D:\AIVoiceStudioData\studio.db`, kết quả phát hiện:
- **Người dùng thử nghiệm**: Tồn tại 01 bản ghi trong bảng `users`:
  - ID: `test_tcp_user`
  - Username: `tcp_victim`
  - Role: `editor`
  - Thời điểm tạo: `2026-10-09 04:25:47`
- **Lịch sử đăng nhập thử nghiệm**: Tồn tại 06 bản ghi trong bảng `login_attempts`:
  - 05 lần thất bại của username `tcp_victim` từ IP `127.0.0.1`.
  - 01 lần thất bại của username `admin` từ IP giả mạo `203.0.113.199`.

**Nguyên nhân gốc rễ (Root Cause)**:
Trong phiên làm việc trước, một lệnh Python kiểm tra socket thủ công (`python -c`) đã được chạy trực tiếp từ dòng lệnh ngoài khuôn khổ pytest mà không cấu hình thư mục dữ liệu tạm. Do đó, script này đã kết nối vào cơ sở dữ liệu mặc định của hệ thống (`studio.db`).

Ngược lại, bài kiểm thử tự động `test_real_tcp_uvicorn_forged_forwarded_headers_rejected_when_untrusted` trong `tests/integration/test_phase5b1_trusted_proxy.py` sử dụng fixture `test_env`, hoàn toàn độc lập trong thư mục tạm `tmp_dir` và **không làm rò rỉ dữ liệu**.

### 3.2. Phương án và Quá trình Dọn dẹp An toàn
Đã tạo và thực thi script chuyên dụng [scripts/cleanup_manual_tcp_test_data.py](file:///d:/C/Dev/du%20an/TTS/scripts/cleanup_manual_tcp_test_data.py):
1. **Tạo bản sao lưu dự phòng vật lý**:
   Sao lưu toàn bộ tệp `studio.db` trước khi can thiệp vào:
   `D:\AIVoiceStudioData\backups\studio_db_pre_cleanup_20261009_061229.db`
2. **Kiểm toán ràng buộc khóa ngoại**:
   Xác minh `test_tcp_user` không có dự án (`projects`), tài sản (`assets`), tác vụ (`jobs`) hay hạn ngạch (`storage_quotas`) liên quan.
3. **Xóa có mục tiêu trong Transaction**:
   Xóa chính xác 01 user `test_tcp_user` và 06 dòng `login_attempts` liên quan.
4. **Xác minh tính toàn vẹn của dữ liệu thực**:
   Tất cả 14 người dùng hợp lệ/Phase 5A, đặc biệt là tài khoản quản trị viên chính `acceptance_qa` (ID: `45051e3d-98e8-4b8c-9958-ff7e4e1b4cb3`), được bảo toàn nguyên vẹn 100%.
5. **Kiểm chứng cô lập cho các bài test tiếp theo**:
   Đã chạy lại bài test tích hợp `test_phase5b1_trusted_proxy.py` và kiểm tra lại `studio.db`: Số lượng bản ghi `tcp_victim` trong database chính vẫn là **0**.

---

## 4. KẾT QUẢ KIỂM THỬ HỢP ĐỒNG & BUILD FRONTEND

### 4.1. Kiểm thử Hợp đồng Engine (`tests/contract/`)
```
======================== 6 passed in 112.30s (0:01:52) ========================
```
- `tests/contract/test_mock_engine.py`: 2/2 PASSED
- `tests/contract/test_qwen3_engine.py`: 2/2 PASSED
- `tests/contract/test_vieneu_engine.py`: 2/2 PASSED
Tất cả các engine manifest, chu kỳ sống worker process và hợp đồng IPC JSON-RPC đều đạt chuẩn.

### 4.2. Build Production Giao diện Web (`apps/web`)
```
> ai-voice-studio-web@1.0.0 build
> tsc && vite build

vite v6.4.4 building for production...
✓ 1604 modules transformed.
dist/index.html                   0.61 kB │ gzip:  0.40 kB
dist/assets/index-CsPuHwNC.css   35.62 kB │ gzip:  6.50 kB
dist/assets/index-DwQcOGcE.js   369.88 kB │ gzip: 99.27 kB
✓ built in 14.67s
```
Bundle production đã được tạo đầy đủ trong `apps/web/dist`.

### 4.3. Kiểm thử Phục vụ SPA Tích hợp
- `tests/integration/test_spa_serving.py`: **1/1 PASSED**.
- `tests/integration/test_phase5b1_trusted_proxy.py`: **17/17 PASSED**.

---

## 5. TÌNH TRẠNG CADDY & HƯỚNG DẪN DÀNH CHO PRODUCT OWNER

### 5.1. Tình trạng Hiện tại: BLOCKED
Lệnh kiểm tra hệ thống `where.exe caddy` và tìm kiếm trong thư mục dự án xác nhận tệp nhị phân `caddy.exe` **chưa có trên máy trạm**. Tuân thủ nghiêm ngặt quy tắc an toàn: **Không tự ý tải về hoặc cài đặt phần mềm từ Internet**.

Mục Runtime Gateway tiếp tục được đánh dấu:
$$\mathbf{Caddy\ Runtime:\ BLOCKED}$$

### 5.2. Hướng dẫn Triển khai Binary Portable Chính thức (Dành cho Quản trị viên)
Khi Product Owner chấp thuận đưa binary vào kiểm thử thực tế, thực hiện theo quy trình sau:

1. **Tải binary chính thức**:
   Tải bản phát hành portable chính thức của Caddy cho Windows 64-bit từ GitHub Releases:
   - URL: `https://github.com/caddyserver/caddy/releases/download/v2.9.1/caddy_2.9.1_windows_amd64.zip`
2. **Xác minh chữ ký số & Hash**:
   Kiểm tra tính toàn vẹn của tệp tải về bằng SHA-256:
   ```powershell
   Get-FileHash -Path "$HOME\Downloads\caddy_2.9.1_windows_amd64.zip" -Algorithm SHA256
   ```
   So sánh với mã băm công bố chính thức trên GitHub Releases của Caddy.
3. **Đặt binary vào dự án**:
   Giải nén `caddy.exe` và đặt vào thư mục `infra/caddy/caddy.exe` (hoặc đặt trong Windows `PATH`).

### 5.3. Quy trình Chạy Kiểm thử Trực tiếp Khi Đã Có Binary
Khi binary đã sẵn sàng:
```powershell
# 1. Định dạng và xác thực cấu hình
.\infra\caddy\caddy.exe fmt --overwrite infra/caddy/Caddyfile
.\infra\caddy\caddy.exe validate --config infra/caddy/Caddyfile

# 2. Xem cấu hình JSON được chuyển đổi
.\infra\caddy\caddy.exe adapt --config infra/caddy/Caddyfile

# 3. Khởi chạy FastAPI Backend (Terminal 1)
.venv\Scripts\python.exe -m apps.server.src.main

# 4. Khởi chạy Caddy Gateway (Terminal 2)
.\infra\caddy\caddy.exe run --config infra/caddy/Caddyfile

# 5. Kiểm tra socket listener chỉ lắng nghe trên 127.0.0.1:9443 (Terminal 3)
Get-NetTCPConnection -LocalPort 9443 | Select-Object LocalAddress, LocalPort, State

# 6. Kiểm tra các chức năng qua HTTPS loopback
curl -k https://127.0.0.1:9443/api/v1/health
```
*(Lưu ý: Không chạy lệnh `caddy trust` để tránh can thiệp vào Windows Certificate Store của máy chủ).*

---

## 6. KẾT LUẬN

1. Tất cả các yêu cầu về rà soát khởi động Uvicorn, cô lập test database, dọn dẹp an toàn và kiểm thử hợp đồng/frontend đều đã hoàn thành xuất sắc và được kiểm chứng.
2. Trạng thái tổng thể được duy trì ở mức **CONDITIONAL PASS** cho đến khi có binary `caddy.exe` để kiểm thử runtime thực tế.
3. Tuyệt đối không mở mạng LAN, không can thiệp firewall và không bắt đầu Phase 5B-2 / Phase 5C.
