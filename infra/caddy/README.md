# AI Voice Studio — Caddy Reverse Proxy & Internal TLS Gateway

Tài liệu hướng dẫn vận hành cổng biên Caddy Reverse Proxy cho AI Voice Studio (Milestone 5B-1).

---

## 1. Mục đích và Kiến trúc Milestone 5B-1

Trong Milestone 5B-1, Caddy Reverse Proxy được cấu hình ở chế độ **Loopback Gateway Staging**:
- **Địa chỉ lắng nghe:** `https://127.0.0.1:9443` (Strictly Loopback only).
- **Backend Upstream:** `http://127.0.0.1:8765` (FastAPI core server).
- **Chứng chỉ TLS:** Sử dụng cơ chế nội bộ **Caddy Internal CA** (`tls internal`), tự động sinh cặp khóa ECDSA/P-256 và chứng chỉ x509 cho IP loopback `127.0.0.1`.
- **Ranh giới an ninh:** Nghiêm cấm phơi bày ra mạng LAN (`0.0.0.0`) hoặc Internet trong Milestone 5B-1.

---

## 2. Trạng thái Môi trường Hiện tại

- **Caddy Executable:** Chưa được cài đặt sẵn trên máy trạm hiện tại (`caddy.exe` không có trong system PATH).
- **Chính sách:** Theo quy chuẩn an toàn của dự án, AI Voice Studio **không tự ý tải về hoặc tự động cài đặt phần mềm bên thứ ba**.
- **Trạng thái nghiệm thu:** Toàn bộ cấu hình `Caddyfile`, cơ chế xử lý `X-Forwarded-For` chống IP spoofing, và bộ kiểm thử tự động Python đã sẵn sàng và được kiểm chứng. Bước kích hoạt tiến trình Caddy thời gian thực được ghi nhận ở trạng thái **CONDITIONAL/BLOCKED** cho đến khi quản trị viên cài đặt tệp nhị phân `caddy.exe`.

---

## 3. Hướng dẫn Cài đặt Caddy cho Quản trị viên (Operator Guide)

### Cách 1: Tải tệp nhị phân chính thức (Portable Binary)
1. Tải bản build chính thức của Caddy cho Windows (amd64) từ:
   `https://caddyserver.com/download` hoặc `https://github.com/caddyserver/caddy/releases`
2. Giải nén tệp `caddy.exe` và đặt vào thư mục trong PATH (ví dụ `C:\Windows\System32` hoặc tạo `tools\caddy.exe` và thêm vào User PATH).

### Cách 2: Cài đặt qua Windows Package Manager
Mở PowerShell (Run as Administrator):
```powershell
winget install CaddyServer.Caddy
# hoặc qua Chocolatey:
choco install caddy
```

---

## 4. Cài đặt Tin cậy Chứng chỉ Nội bộ (Trust Root CA)

Để trình duyệt web (Chrome, Edge) hoặc `curl` không báo lỗi cảnh báo chứng chỉ tự ký (`SEC_ERROR_UNKNOWN_ISSUER` hoặc `CERT_AUTHORITY_INVALID`):

1. **Tự động tin cậy qua Caddy CLI (Yêu cầu quyền Administrator):**
   ```powershell
   caddy trust
   ```
   Lệnh này tự động đưa Caddy Local Authority Root Certificate vào Windows Certificate Store (`Cert:\CurrentUser\Root` hoặc `Cert:\LocalMachine\Root`).

2. **Cài đặt thủ công bằng certutil:**
   Chứng chỉ Root CA của Caddy được lưu tại:
   `$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt`
   Cài đặt chứng chỉ bằng lệnh:
   ```powershell
   certutil -addstore -f "Root" "$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt"
   ```

---

## 5. Quy trình Kiểm tra và Khởi chạy

### Bước 1: Kiểm tra cú pháp tệp cấu hình
```powershell
caddy validate --config infra/caddy/Caddyfile
```
*Kết quả kỳ vọng:* `Valid configuration`.

### Bước 2: Khởi chạy FastAPI Backend (Terminal 1)
```powershell
# Khởi chạy qua module chuẩn hóa (Tự động áp dụng UVICORN_PROXY_HEADERS=False):
.venv\Scripts\python.exe -m apps.server.src.main

# Hoặc nếu chạy trực tiếp qua Uvicorn CLI, bắt buộc truyền cờ vô hiệu hóa ProxyHeaders:
.venv\Scripts\python.exe -m uvicorn apps.server.src.main:app --host 127.0.0.1 --port 8765 --no-proxy-headers --forwarded-allow-ips ""
```

### Bước 3: Khởi chạy Caddy Reverse Proxy (Terminal 2)
```powershell
caddy run --config infra/caddy/Caddyfile
```

### Bước 4: Kiểm tra kết nối HTTPS Loopback (Terminal 3)
```powershell
# Kiểm tra Health Check qua cổng HTTPS Staging
curl -v https://127.0.0.1:9443/api/v1/health

# Hoặc bỏ qua xác thực chứng chỉ trong giai đoạn kiểm thử sơ bộ:
curl -k https://127.0.0.1:9443/api/v1/health
```

*Kết quả kỳ vọng:*
- HTTP 200 OK
- Headers trả về bao gồm:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - Header `Server` đã bị loại bỏ hoặc che giấu.
