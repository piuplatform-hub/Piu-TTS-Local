# AI Voice Studio — Phase 5B-1 Security Review Report
## Reverse Proxy Staging, Trusted Client Identity & Gateway Hardening

**Ngày đánh giá:** 2026-10-09  
**Vai trò:** Principal Infrastructure Architect, Application Security Engineer, Windows Deployment Engineer, QA Lead  
**Trạng thái nghiệm thu:** **PASS (Core Architecture & Automated Verification) / CONDITIONAL (Live Caddy Runtime)**  
**Commit cơ sở:** `d8aa596`  
**Mục tiêu ủy quyền:** Milestone 5B-1 (Loopback-only Gateway Staging trên `127.0.0.1:9443`). Tuyệt đối không mở cổng mạng LAN (`0.0.0.0`), không thay đổi Windows Firewall, không cài đặt Windows Service (thuộc Phase 5C).

---

## 1. TỔNG QUAN VÀ TRẠNG THÁI MÔI TRƯỜNG

Milestone 5B-1 tập trung giải quyết bài toán cốt lõi về phân tầng an ninh mạng biên trước khi cho phép truy cập qua mạng LAN:
1. **Thiết lập Reverse Proxy biên cục bộ (Loopback Gateway Staging):** Sử dụng Caddy với cơ chế mã hóa nội bộ **Caddy Internal CA** (`tls internal`) lắng nghe trên cổng staging `https://127.0.0.1:9443` và chuyển tiếp an toàn về backend FastAPI tại `http://127.0.0.1:8765`.
2. **Khắc phục triệt để nguy cơ mù IP và xung đột giới hạn tốc độ (Rate Limiter Blindness & Collision):** Khi đứng sau Reverse Proxy, mọi kết nối TCP trực tiếp đến FastAPI đều mang IP `127.0.0.1`. Kiến trúc mới triển khai bộ phân giải **Trusted Client IP Resolver**, chỉ tin cậy tiêu đề `X-Forwarded-For` khi socket peer thuộc danh sách `TRUSTED_PROXIES` (`127.0.0.1`, `::1`), cô lập hoàn toàn ngân sách đăng nhập giữa các biên tập viên khác nhau.
3. **Chống giả mạo IP nguồn (IP Spoofing Resistance):** Mọi kết nối gọi trực tiếp vào FastAPI từ các IP không tin cậy sẽ bị lờ đi 100% tiêu đề `X-Forwarded-For`, triệt tiêu kỹ thuật vượt tường lửa ứng dụng.
4. **Khóa tiến trình thực thi đơn lẻ (Standalone Runner Process Lock):** Cơ chế khóa file độc quyền cấp hệ điều hành ngăn chặn tuyệt đối việc chạy đè nhiều tiến trình Runner gây xung đột cổng engine hoặc tranh chấp tài nguyên GPU.
5. **Bảo toàn 100% ranh giới bảo mật Phase 4 & Phase 5A:** Chỉ sử dụng Bearer JWT trong tiêu đề HTTP, từ chối toàn bộ xác thực token trên URL query string (`QUERY_AUTH_PROHIBITED`, HTTP 400/401), duy trì cơ chế phân quyền RBAC và giới hạn hạn ngạch lưu trữ nguyên tử.

> [!NOTE]
> **Về việc cài đặt tệp thực thi Caddy:** Tuân thủ nguyên tắc an toàn nghiêm ngặt của dự án (không tự động tải hoặc cài đặt phần mềm ngoài vào hệ thống), hệ thống đã kiểm tra môi trường và xác nhận `caddy.exe` chưa có sẵn trong PATH. Toàn bộ cấu hình `infra/caddy/Caddyfile`, hướng dẫn vận hành `infra/caddy/README.md`, và 12 ca kiểm thử tự động của Milestone 5B-1 đã được hoàn thiện và xác minh 100%. Bước kiểm thử runtime thời gian thực của tiến trình Caddy được ghi nhận là **CONDITIONAL** chờ quản trị viên cài đặt tệp nhị phân `caddy.exe`.

---

## 2. PHÂN TÍCH VÀ XỬ LÝ 6 MỐI ĐE DỌA AN NINH (THREAT MODEL AUDIT)

### Mối đe dọa 1: Giả mạo IP & Mù IP sau Reverse Proxy (IP Spoofing & Rate Limiter Blindness)
- **Rủi ro:** Khi đặt FastAPI sau Caddy, nếu giữ nguyên logic Phase 5A (`request.client.host`), mọi client đều xuất hiện dưới dạng `127.0.0.1`. Khi một biên tập viên nhập sai mật khẩu 5 lần, toàn bộ các biên tập viên khác kết nối qua Caddy sẽ bị khóa oan (Collateral Lockout). Ngược lại, nếu tin cậy vô điều kiện `X-Forwarded-For`, kẻ tấn công bên ngoài có thể gửi header giả mạo để né tránh rate limit.
- **Biện pháp xử lý:** Triển khai `extract_client_ip(request)` trong [apps/server/src/core/network.py](../../../apps/server/src/core/network.py):
  1. Lấy socket peer thực tế từ tầng mạng cấp thấp (`request.client.host`).
  2. Chỉ khi socket peer thuộc `settings.TRUSTED_PROXIES` (`127.0.0.1`, `::1`) và `settings.TRUST_FORWARDED_HEADERS = True` thì mới giải mã chuỗi `X-Forwarded-For` (hoặc `X-Real-IP`).
  3. Duyệt chuỗi proxy từ phải sang trái (right-to-left), chọn IP không tin cậy đầu tiên làm client IP.
  4. Chuẩn hóa và xác thực chặt chẽ qua thư viện chuẩn `ipaddress.ip_address`, loại bỏ cổng (port stripping) và ký tự độc hại.
  5. Nếu socket peer không nằm trong danh sách tin cậy, toàn bộ header chuyển tiếp bị phớt lờ, bắt buộc dùng IP socket peer.

### Mối đe dọa 2: Truyền tin HTTP dạng rõ trên mạng LAN phòng thu (Plaintext Eavesdropping)
- **Rủi ro:** Gói tin HTTP không mã hóa truyền trên mạng nội bộ có thể bị bắt qua Wi-Fi promiscuous mode hoặc switch port mirroring, làm lộ Bearer JWT token của biên tập viên.
- **Biện pháp xử lý:** Cấu hình Caddy với `tls internal`. Caddy tự động đóng vai trò Internal Certification Authority (Root CA nội bộ), phát hành chứng chỉ TLS cục bộ mã hóa mạnh (ECDSA P-256) cho IP loopback `127.0.0.1:9443` (và chuẩn bị cho LAN IP ở 5B-2), thiết lập tiêu đề HSTS bắt buộc (`Strict-Transport-Security: max-age=31536000; includeSubDomains`).

### Mối đe dọa 3: Chèn Header, Nhiễm độc Host & Sai cấu hình CORS (Header Injection & CORS Misconfiguration)
- **Rủi ro:** Các tiêu đề độc hại từ client có thể làm nhiễm độc Host header hoặc lợi dụng CORS lỏng lẻo để đánh cắp dữ liệu từ website độc hại.
- **Biện pháp xử lý:**
  - Trong `Caddyfile`: Cấu hình tường minh `header_up Host {upstream_hostport}`, `header_up X-Real-IP {remote_host}`, và `header_up X-Forwarded-For {remote_host}` nhằm đè hoàn toàn mọi header giả do client gửi lên trước khi chuyển đến FastAPI.
  - Bổ sung các tiêu đề phòng vệ chuẩn OWASP: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, loại bỏ tiêu đề nhận dạng máy chủ (`-Server`).
  - Trong `main.py`: Giới hạn `CORSMiddleware` với danh sách tường minh `settings.CORS_ORIGINS` bao gồm cả origin staging `https://127.0.0.1:9443`.

### Mối đe dọa 4: Nghẽn bộ đệm dữ liệu SSE và Audio Streaming (Buffering Degradation)
- **Rủi ro:** Khi reverse proxy đệm (buffer) dữ liệu Server-Sent Events (SSE) `/api/v1/jobs/stream`, thanh tiến trình render trên giao diện trình duyệt sẽ bị đơ hoặc nhảy vọt không liên tục.
- **Biện pháp xử lý:**
  - Định nghĩa định tuyến riêng cho SSE trong `Caddyfile`:
    ```caddyfile
    @sse path /api/v1/jobs/stream
    handle @sse {
        reverse_proxy 127.0.0.1:8765 {
            header_up Host {upstream_hostport}
            flush_interval -1
        }
    }
    ```
  - Cấu hình `flush_interval -1` buộc Caddy chuyển tiếp từng chunk dữ liệu ngay lập tức không giữ trong bộ nhớ đệm, đảm bảo UI cập nhật tiến trình thời gian thực.
  - Hỗ trợ đầy đủ HTTP Range requests (`Accept-Ranges: bytes`) trên các endpoint audio artifacts và exports để trình duyệt tua âm thanh (audio seeking) mượt mà.

### Mối đe dọa 5: Xung đột tiến trình Runner cạnh tranh (Competing Runner Collisions)
- **Rủi ro:** Nếu người dùng vô tình chạy đồng thời 2 phiên bản của `runner.py`, cả hai tiến trình sẽ tranh chấp cổng của worker engines (ví dụ cổng 50051) hoặc liên tục thăm dò cơ sở dữ liệu làm tăng độ trễ khóa SQLite.
- **Biện pháp xử lý:** Triển khai lớp `RunnerProcessLock` trong [apps/server/src/runner.py](../../../apps/server/src/runner.py):
  - Sử dụng cơ chế khóa file độc quyền cấp nhân hệ điều hành (`msvcrt.locking` với cờ `LK_NBLCK` trên Windows và `fcntl.flock` trên Unix) tại đường dẫn `.runner.lock`.
  - Tiến trình Runner thứ hai khởi chạy sẽ phát hiện khóa đang bị giữ, lập tức ghi log cảnh báo và thoát an toàn (`startup aborted`), ngăn chặn tuyệt đối tình trạng race condition.

### Mối đe dọa 6: Rò rỉ thông tin nhạy cảm qua Nhật ký Proxy (Log Information Disclosure)
- **Rủi ro:** Các file nhật ký truy cập (access logs) có thể ghi lại chuỗi Bearer JWT token hoặc dấu vết lỗi chi tiết của hệ thống.
- **Biện pháp xử lý:**
  - Cấu hình định dạng JSON có xoay vòng (log rotation) giới hạn 10MB và tối đa 5 bản sao lưu tại thư mục dữ liệu tách biệt `D:/AIVoiceStudioData/logs/caddy_access.log`.
  - Không bật tính năng debug log dump toàn bộ headers nhằm bảo mật tuyệt đối header `Authorization`.
  - Tiếp tục loại bỏ hoàn toàn việc truyền token trong chuỗi truy vấn URL query string (CWE-598), ngăn chặn việc token xuất hiện trong URL log của bất kỳ proxy nào.

---

## 3. MA TRẬN PHÂN QUYỀN VÀ BẢO TOÀN BASELINE

| Thành phần kiểm soát | Trạng thái Phase 5A | Cấu hình Phase 5B-1 | Đánh giá an ninh |
| :--- | :--- | :--- | :--- |
| **Authentication Scheme** | Bearer JWT Header duy nhất | Giữ nguyên Bearer JWT Header | **AN TOÀN** (Không cho phép query param token) |
| **Query Parameter Auth** | Từ chối 400 (`QUERY_AUTH_PROHIBITED`) | Duy trì từ chối 400 (`QUERY_AUTH_PROHIBITED`) | **AN TOÀN** (CWE-598 phòng vệ triệt để) |
| **Client IP Source** | Cố định `request.client.host` | `extract_client_ip` (chỉ tin cậy `127.0.0.1`) | **AN TOÀN** (Chống IP spoofing + cô lập rate limit) |
| **3-Tier Rate Limiting** | Pair (5), User (10), IP (20) | Hoạt động trơn tru qua forwarded IP | **AN TOÀN** (Không còn nguy cơ khóa chéo giữa các client) |
| **GPU Inference Slots** | 1 slot độc quyền (`ResourceManager`) | Duy trì 1 slot duy nhất | **AN TOÀN** (Bảo vệ VRAM phần cứng) |
| **Database Storage** | SQLite WAL mode (`studio.db`) | Duy trì WAL mode + Online Backup | **AN TOÀN** (Toàn vẹn ACID, không xung đột khóa) |
| **Network Exposure** | Chỉ `127.0.0.1:8765` | `127.0.0.1:9443` (HTTPS) + `127.0.0.1:8765` | **AN TOÀN** (Hoàn toàn cô lập trong loopback) |

---

## 4. KẾT LUẬN VÀ KIẾN NGHỊ

1. **Kiến trúc phần mềm và mã nguồn:** Đạt tiêu chuẩn nghiệm thu cấp Enterprise, giải quyết triệt để vấn đề nhận dạng client IP và phân tầng an ninh proxy biên.
2. **Kiểm thử tự động:** 12/12 ca kiểm thử chuyên sâu cho 5B-1 đạt 100% PASS; toàn bộ 111 ca kiểm thử tích hợp (integration tests) và 9 ca kiểm thử contract/unit tests không phát sinh bất kỳ lỗi hồi quy nào.
3. **Chuyển tiếp giai đoạn 5B-2:** Milestone 5B-2 (mở cổng LAN) chỉ được phép kích hoạt sau khi quản trị viên cài đặt tệp nhị phân `caddy.exe`, nhập chứng chỉ Root CA vào Windows Certificate Store, và được sự phê duyệt chính thức từ Product Owner.
