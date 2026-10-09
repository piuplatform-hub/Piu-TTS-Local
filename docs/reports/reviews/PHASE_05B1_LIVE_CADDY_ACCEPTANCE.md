# AI VOICE STUDIO — BÁO CÁO NGHIỆM THU PHASE 5B-1 FINAL LIVE CADDY ACCEPTANCE
## CỔNG BẢO MẬT CADDY REVERSE PROXY, XÁC THỰC TLS NGHIÊM NGẶT & SAO LƯU TRỰC TUYẾN SQLITE

- **Dự án**: AI Voice Studio
- **Kiến trúc**: R1.1 (FastAPI Core Backend + Vite/React Frontend + Kokoro/Qwen3/VieNeu Engines)
- **Giai đoạn**: Phase 5B-1 Final Live Caddy Acceptance — Nghiệm thu Cổng Caddy Reverse Proxy & TLS Loopback
- **Ngày thực hiện**: 2026-10-09
- **Người thực hiện**: Principal Infrastructure Architect, Application Security Engineer, Windows Deployment Engineer, QA Lead
- **Commit cơ sở**: `01051ba`
- **Đánh giá Cổng Nghiệm thu**: **FULL PASS** (Hoàn thành 100% tiêu chí an ninh, kỹ thuật và kiểm thử hồi quy)

---

## 1. TỔNG QUAN VÀ TUYÊN BỐ NGHIỆM THU

Milestone **Phase 5B-1** đánh dấu bước hoàn thiện việc đóng gói và triển khai thử nghiệm cổng biên bảo mật Reverse Proxy (Caddy v2.9.1) trên môi trường Windows x64. Mọi hoạt động triển khai được kiểm soát tuyệt đối trên giao diện loopback nội bộ (`127.0.0.1`, cổng `9443`), tuân thủ nghiêm ngặt các rào cản an ninh:
1. **Không mở mạng LAN (`0.0.0.0`)**, không thay đổi cấu hình tường lửa Windows Firewall.
2. **Không đăng ký Windows Service** (giữ lại cho Phase 5C).
3. **Không cài đặt Root CA vào Windows hoặc Browser Certificate Store** (`Cert:\CurrentUser\Root`, `Cert:\LocalMachine\Root` giữ nguyên trạng sạch 100%).
4. **Không sử dụng cờ vô hiệu hóa bảo mật** (`curl -k` hay `ignore_https_errors=True` trong Playwright) để giả lập vượt qua kiểm tra an ninh; áp dụng cơ chế xác thực chứng chỉ nghiêm ngặt và ghim khóa công khai SPKI (Subject Public Key Info pinning).
5. **Cơ sở dữ liệu chính không bị nhiễm bẩn**: Toàn bộ kiểm thử chạy trên cơ sở dữ liệu tạm cô lập; cơ sở dữ liệu chính `D:\AIVoiceStudioData\studio.db` được bảo toàn toàn vẹn và có bản sao lưu trực tuyến đã kiểm chứng tính toàn vẹn bằng `PRAGMA integrity_check`.

Căn cứ vào kết quả kiểm thử thực tế trên hệ thống trực tiếp, chúng tôi tuyên bố **FULL PASS** cho Milestone **Phase 5B-1**.

---

## 2. TẢI VỀ VÀ XÁC MINH MÃ HÓA CADDY PORTABLE

### 2.1. Nguồn Gốc và Phiên Bản
- **Phiên bản**: Caddy v2.9.1 (Bản phát hành chính thức ổn định dành cho Windows x64)
- **Địa chỉ tải về**: `https://github.com/caddyserver/caddy/releases/download/v2.9.1/caddy_2.9.1_windows_amd64.zip`
- **Tệp chữ ký checksum chính thức**: `https://github.com/caddyserver/caddy/releases/download/v2.9.1/caddy_2.9.1_checksums.txt`

### 2.2. Kết Quả Xác Minh Băm Mật Mã
- **Mã băm SHA-512 chính thức công bố**:
  ```
  4f0f85b42015ff2276d08705751472e6a98bdc7fda5ec76dd41b7a0c16fee90af012f1a7beb226164408cfbe656bd3453ed5ccbb596f80c45d0fa1c749fc8da2
  ```
- **Mã băm SHA-512 tệp zip tải về**: Khớp 100% (`4f0f85b...c8da2`).
- **Mã băm SHA-256 tệp zip**: `fc99862101cd015a1fd2c1b38376109b543a5de5b6fa63ecf35a491b41e3613a`
- **Mã băm SHA-256 binary giải nén `infra/caddy/caddy.exe`**:
  ```
  95916e32a8115f3c39747647d83b8c9a8d80a0f401cf86ab8ba8d974c01c646e
  ```
- **Xác minh phiên bản thực tế**:
  ```powershell
  .\infra\caddy\caddy.exe version
  # Kết quả: v2.9.1 h1:OEYiZ7DbCzAWVb6TNEkjRcSCRGHVoZsJinoDR/n9oaY=
  ```

### 2.3. Khóa Chặt Git Repository
Đã bổ sung các mẫu đường dẫn vào `.gitignore` để đảm bảo tệp thực thi nhị phân, khóa bí mật và chứng chỉ tự sinh không bị commit vào Git:
```gitignore
# Caddy Local Gateway Artifacts
caddy.exe
infra/caddy/caddy.exe
infra/caddy/LICENSE
infra/caddy/data/
infra/caddy/pki/
.caddy/
*.crt
*.key
*.pem
```

---

## 3. BẢO VỆ ROOT CA & TOÀN VẸN TRUST STORE HỆ ĐIỀU HÀNH

### 3.1. Chỉ Thị `skip_install_trust`
Trong [infra/caddy/Caddyfile](file:///d:/C/Dev/du%20an/TTS/infra/caddy/Caddyfile), khối cấu hình toàn cục đã bổ sung tường minh:
```caddy
{
    admin off
    auto_https disable_redirects
    skip_install_trust
}
```
Chỉ thị `skip_install_trust` ngăn Caddy gọi API hệ thống Windows CryptoAPI để thêm chứng chỉ CA vào kho lưu trữ tin cậy của máy tính người dùng mà không có sự đồng ý.

### 3.2. Bằng Chứng Kiểm Tra Kho Chứng Chỉ Windows
Thực thi kiểm tra kho chứng chỉ `Cert:\CurrentUser\Root` và `Cert:\LocalMachine\Root`:
```powershell
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -like "*Caddy*" }
# Kết quả: Trả về rỗng (0 chứng chỉ)

Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*Caddy*" }
# Kết quả: Trả về rỗng (0 chứng chỉ)
```
Chứng chỉ Root CA được Caddy sinh ra cục bộ chỉ lưu tại thư mục profile người dùng cô lập:
`C:\Users\OS\AppData\Roaming\Caddy\pki\authorities\local\root.crt`.

---

## 4. XÁC MINH CẤU HÌNH VÀ BINDING SOCKET

### 4.1. Kiểm Tra Cấu Hình Caddy
- `caddy validate`:
  ```powershell
  .\infra\caddy\caddy.exe validate --config infra/caddy/Caddyfile
  # Kết quả: Valid configuration
  ```
- `caddy adapt`: Kiểm tra cấu hình JSON nội bộ của Caddy:
  ```json
  {
    "admin": { "disabled": true },
    "apps": {
      "pki": {
        "certificate_authorities": {
          "local": {
            "install_trust": false
          }
        }
      },
      "http": {
        "servers": {
          "srv0": {
            "listen": ["127.0.0.1:9443"]
          }
        }
      }
    }
  }
  ```

### 4.2. Bằng Chứng Ràng Buộc Socket (Socket Binding)
Khi Caddy đang hoạt động, truy vấn kết nối TCP kernel Windows:
```powershell
Get-NetTCPConnection -LocalPort 9443 -State Listen | Select-Object LocalAddress, LocalPort, State
```
| LocalAddress | LocalPort | State | Ghi Chú |
| :--- | :--- | :--- | :--- |
| `127.0.0.1` | `9443` | `Listen` | Ràng buộc duy nhất trên loopback, không mở `0.0.0.0` |

---

## 5. XÁC THỰC TLS NGHIÊM NGẶT & GHIM KHÓA SPKI

### 5.1. Kiểm Tra Bác Bỏ Kết Nối Thiếu Chứng Chỉ Tin Cậy
Thực hiện yêu cầu HTTPS không cung cấp root CA qua Python `httpx`:
```python
with httpx.Client(verify=True) as client:
    client.get("https://127.0.0.1:9443/api/v1/health")
```
- **Kết quả**: Thất bại với lỗi `SSLCertVerificationError` (`unable to get local issuer certificate`), chứng minh kết nối qua Caddy áp dụng TLS xác thực nghiêm ngặt, không thể bị qua mặt nếu không có chứng chỉ tin cậy hợp lệ.

### 5.2. Ghim Khóa Công Khai SPKI (Subject Public Key Info Pinning) Cho Browser E2E
Để thực hiện kiểm thử E2E trên Google Chrome thực tế mà không cần thêm root CA vào hệ điều hành và không sử dụng `ignore_https_errors=True`:
- Trích xuất cấu trúc ASN.1 DER của Leaf Certificate (`127.0.0.1.crt`) và Root Certificate (`root.crt`).
- Tính toán mã băm SHA-256 Base64 của `SubjectPublicKeyInfo`:
  - **Leaf SPKI**: `J1OxpA/7W7XHBy/MfaV3trVj/RC5ltlj4OJCLtVfFlM=`
  - **Root SPKI**: `LGk3TRqlmtCLTZui1dPvMdlWy9TqBrjYi9qo8qej8lI=`
- Truyền tham số ghim khóa cho Chrome:
  `--ignore-certificate-errors-spki-list=J1OxpA/7W7XHBy/MfaV3trVj/RC5ltlj4OJCLtVfFlM=,LGk3TRqlmtCLTZui1dPvMdlWy9TqBrjYi9qo8qej8lI=`
- Kết quả kiểm chứng:
  - Khi khóa SPKI khớp: Chrome kết nối HTTPS thành công và Playwright chạy với `ignore_https_errors=False`.
  - Khi giả mạo khóa SPKI sai: Chrome lập tức chặn kết nối với lỗi `net::ERR_CERT_AUTHORITY_INVALID`.

---

## 6. KIỂM THỬ TRÌNH DUYỆT THỰC TẾ (REAL BROWSER E2E)

Bộ kiểm thử [tests/e2e/test_phase5b1_caddy_https_e2e.py](file:///d:/C/Dev/du%20an/TTS/tests/e2e/test_phase5b1_caddy_https_e2e.py) đã thực hiện trọn vẹn luồng công việc trên Google Chrome thật:
1. Truy cập `https://127.0.0.1:9443/` qua kết nối HTTPS bảo mật.
2. Đăng nhập tài khoản quản trị viên `caddy_admin`.
3. Kiểm tra danh sách dự án, mở dự án narration `Caddy HTTPS Gateway E2E Project`.
4. Mở giao diện Studio, kiểm tra hiển thị phân đoạn văn bản, huy hiệu hoàn thành và các điều khiển xuất bản.
5. Chụp ảnh màn hình chứng cứ xác thực:
   - Tệp: [docs/reports/screenshots/phase5b1_01_caddy_https_browser_verified.png](file:///d:/C/Dev/du%20an/TTS/docs/reports/screenshots/phase5b1_01_caddy_https_browser_verified.png)
   - Kích thước: 68,763 bytes.
   - Nội dung ảnh: Thể hiện rõ người dùng `caddy_admin (ADMIN)`, dự án narration với 1 phân đoạn đã hoàn thành, nút `Nghe thử` và nút `Xuất Bản Master DSP`.

---

## 7. RATE LIMITING & NHẬN DẠNG CLIENT PHÍA SAU REVERSE PROXY

### 7.1. Chống Giả Mạo Client IP
Caddyfile được cấu hình chỉ thị:
```caddy
reverse_proxy 127.0.0.1:8765 {
    header_up Host {upstream_hostport}
    header_up X-Real-IP {remote_host}
    header_up X-Forwarded-For {remote_host}
    header_up X-Forwarded-Proto {scheme}
}
```
Caddy ghi đè tiêu đề `X-Forwarded-For` bằng `{remote_host}` thực tế từ socket TCP của client, loại bỏ khả năng client bên ngoài gửi header `X-Forwarded-For` giả mạo để vượt qua giới hạn rate limit.

### 7.2. Kiểm Thử Khóa Tài Khoản (Rate Limit Lockout)
Thực hiện gửi liên tiếp 5 yêu cầu đăng nhập sai mật khẩu qua cổng HTTPS `https://127.0.0.1:9443/api/v1/auth/login`:
- Lần 1 đến 5: Trả về HTTP 401 `INCORRECT_CREDENTIALS`.
- Lần thứ 6: Trả về HTTP 429 `TOO_MANY_LOGIN_ATTEMPTS` kèm mã lỗi RFC 9457 chi tiết.
- Các tài khoản hợp lệ khác không bị ảnh hưởng.

### 7.3. Nhật Ký Truy Cập Caddy (Structured Access Log)
Tệp nhật ký `D:/AIVoiceStudioData/logs/caddy_access.log` được tạo dưới định dạng JSON có cấu trúc. Rà soát 100% bản ghi cho thấy:
- Không tồn tại token xác thực trên URL (`token=` query string không xuất hiện).
- Mọi tiêu đề nhạy cảm được bảo vệ an toàn.

---

## 8. KIỂM TOÁN DỮ LIỆU & SAO LƯU TRỰC TUYẾN SQLITE

### 8.1. Kiểm Toán Tính Toàn Vẹn Cơ Sở Dữ Liệu Chính
Kiểm tra cơ sở dữ liệu production tại `D:\AIVoiceStudioData\studio.db`:
```python
con = sqlite3.connect('D:/AIVoiceStudioData/studio.db')
cur = con.cursor()
cur.execute('PRAGMA integrity_check;')
# Kết quả: ok
cur.execute('SELECT COUNT(*) FROM users;')
# Kết quả: 14 (Chính xác số lượng người dùng hợp lệ)
cur.execute('SELECT COUNT(*) FROM users WHERE username LIKE "%caddy%";')
# Kết quả: 0 (Không bị lọt dữ liệu thử nghiệm)
cur.execute('SELECT COUNT(*) FROM login_attempts WHERE username LIKE "%caddy%";')
# Kết quả: 0 (Không bị lọt bản ghi đăng nhập thử nghiệm)
```

### 8.2. Đánh Giá Sao Lưu R1 & Triển Khai Sao Lưu Trực Tuyến Chính Xác (Item 7)
- **Đánh giá bản sao lưu R1**: Bản sao lưu trước đây được thực hiện bằng `shutil.copy2` khi SQLite đang mở ở chế độ WAL mode. Theo tài liệu chính thức của SQLite, sao chép tệp đơn thuần trong khi đang có giao dịch ghi WAL có thể dẫn đến trạng thái không đồng bộ (bản sao lưu thiếu checkpoint). Bản sao lưu R1 được xếp loại **UNVERIFIED**.
- **Giải pháp khắc phục**: Đã xây dựng công cụ chuẩn mực [scripts/create_verified_online_backup.py](file:///d:/C/Dev/du%20an/TTS/scripts/create_verified_online_backup.py) sử dụng `sqlite3.Connection.backup()` (SQLite Online Backup API).
- **Kết quả sao lưu trực tuyến đã kiểm chứng**:
  - Tệp sao lưu: `D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db`
  - Kích thước: 131,072 bytes.
  - Kiểm tra tính toàn vẹn: `PRAGMA integrity_check` -> `ok`.
  - Số lượng người dùng: 14; Số lượng dự án: 9.

---

## 9. MA TRẬN KẾT QUẢ TOÀN BỘ BỘ TEST HỒI QUY

| Hạng mục kiểm thử | Phạm vi | Số lượng test | Kết quả | Thời gian |
| :--- | :--- | :--- | :--- | :--- |
| **Unit Tests** | Phân đoạn văn bản tiếng Việt & tiếng Trung | 3/3 | **PASS** | 0.04s |
| **Contract Tests** | Tuân thủ Engine SDK & Manifest (Mock, Qwen3, VieNeu) | 6/6 | **PASS** | 128.75s |
| **Integration Tests** | Quota, RBAC, Rate Limiting, Preflight, Queue & Caddy | 117/117 | **PASS** | ~265s |
| **Browser E2E (Phase 1-4)** | Trình duyệt thực tế (Studio, Export WAV/MP3) | 4/4 | **PASS** | ~55s |
| **Browser E2E (Phase 5B-1)** | Caddy HTTPS (SPKI Pinning, Full UI Journey) | 1/1 | **PASS** | 9.16s |
| **Frontend Production Build** | TypeScript compiler & Vite bundle | 1/1 | **PASS** | 17.15s |
| **Tổng cộng** | **Toàn bộ hệ thống AI Voice Studio** | **132/132** | **PASS 100%** | - |

---

## 10. KẾT LUẬN VÀ KIẾN NGHỊ

1. **Kết Luận**: Milestone **Phase 5B-1** đã đạt toàn diện mọi tiêu chuẩn chất lượng và an ninh kỹ thuật. Cổng Reverse Proxy Caddy hoạt động ổn định trên `127.0.0.1:9443` với chứng chỉ nội bộ cô lập, cơ chế xác thực client IP chính xác, bảo toàn trọn vẹn toàn bộ các tính năng từ Phase 0 đến Phase 5A.
2. **Kiến Nghị Vận Hành**:
   - Duy trì `skip_install_trust` trong cấu hình Caddyfile.
   - Không commit tệp binary hoặc khóa bí mật vào Git.
   - Luôn sử dụng SQLite Online Backup API khi thực hiện sao lưu định kỳ.
   - **Phase 5B-1 CHÍNH THỨC ĐÓNG LẠI (FULL PASS).** Sẵn sàng để Product Owner đánh giá và phê duyệt chuyển sang các bước lập kế hoạch tiếp theo khi có chỉ thị.
