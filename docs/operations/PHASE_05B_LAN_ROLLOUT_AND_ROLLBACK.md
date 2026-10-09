# AI Voice Studio — Milestone 5B-2: LAN Rollout & Rollback Runbook

> [!CAUTION]
> **TÀI LIỆU QUY TRÌNH CHƯA THỰC THI (UNEXECUTED)**  
> Bản hướng dẫn này được lập cho **Milestone 5B-2 (Phơi bày mạng LAN phòng thu)**.  
> Trong phạm vi **Milestone 5B-1**, tài liệu này **TUYỆT ĐỐI CHƯA ĐƯỢC PHÉP THỰC THI**. Không được tự ý mở cổng tường lửa hay thay đổi binding IP sang `0.0.0.0` hoặc IP mạng LAN cho đến khi có sự phê chuẩn chính thức của Product Owner.

---

## 1. MỤC TIÊU VÀ ĐIỀU KIỆN TIÊN QUYẾT (PRE-ROLLOUT CHECKLIST)

Chỉ bắt đầu triển khai Milestone 5B-2 khi thỏa mãn 100% các điều kiện sau:
- [ ] Milestone 5B-1 đã được nghiệm thu hoàn tất với 100% ca kiểm thử tự động PASS.
- [ ] Tệp thực thi `caddy.exe` đã được cài đặt vào hệ thống và kiểm tra hợp lệ (`caddy version`).
- [ ] Đã thực hiện sao lưu trực tuyến cơ sở dữ liệu (`python -m apps.server.src.backup create`) và xác minh SHA256 thành công.
- [ ] Quản trị viên phòng thu và Product Owner đã ký duyệt ủy quyền mở cổng LAN.
- [ ] Máy trạm Windows đang kết nối vào profile mạng **Private Network** (không phải Public Network).

---

## 2. QUY TRÌNH TRIỂN KHAI TỪNG BƯỚC (ROLLOUT PROCEDURE)

### Bước 1: Xác định địa chỉ IP mạng LAN của máy trạm phòng thu
Mở PowerShell và chạy lệnh:
```powershell
Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*", "Wi-Fi*" | 
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | 
    Select-Object IPAddress, InterfaceAlias
```
*Giả sử IP mạng LAN xác định được là: `192.168.1.15`.*

### Bước 2: Thiết lập Tường lửa Windows (Windows Firewall Rule)
Chỉ mở cổng 9443 và **giới hạn nghiêm ngặt trong phân vùng mạng Private (Nội bộ)**:
```powershell
# Chạy với quyền Administrator
New-NetFirewallRule -DisplayName "AI Voice Studio HTTPS Gateway" `
    -Direction Inbound `
    -LocalPort 9443 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private `
    -Description "Reverse Proxy HTTPS inbound access for Studio editors"
```
*Tuyệt đối không áp dụng cho Profile `Public`.*

### Bước 3: Cập nhật cấu hình Caddyfile cho LAN IP
Chuyển đổi binding trong `infra/caddy/Caddyfile`:
```caddyfile
{
    admin off
    auto_https disable_redirects
}

https://192.168.1.15:9443 {
    tls internal

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    @sse path /api/v1/jobs/stream
    handle @sse {
        reverse_proxy 127.0.0.1:8765 {
            header_up Host {upstream_hostport}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
            flush_interval -1
        }
    }

    handle {
        reverse_proxy 127.0.0.1:8765 {
            header_up Host {upstream_hostport}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    log {
        output file D:/AIVoiceStudioData/logs/caddy_access.log {
            roll_size 10mb
            roll_keep 5
        }
        format json
    }
}
```

### Bước 4: Cài đặt chứng chỉ Root CA trên các máy tính biên tập viên
1. Xuất file Root CA từ máy chủ:
   `$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt`
2. Phân phối file `root.crt` tới máy khách của các biên tập viên.
3. Trên máy khách (Windows), nhập chứng chỉ vào kho chứng chỉ tin cậy:
   ```powershell
   certutil -addstore -f "Root" root.crt
   ```

### Bước 5: Khởi chạy và Nghiệm thu từ máy khách (Client Acceptance Testing)
1. Trên máy chủ, khởi chạy FastAPI (vẫn giữ nguyên `127.0.0.1:8765`) và Caddy.
2. Từ máy tính biên tập viên khác trong mạng LAN, mở trình duyệt truy cập:
   `https://192.168.1.15:9443`
3. Kiểm tra:
   - Trình duyệt hiển thị biểu tượng ổ khóa an toàn (Valid TLS).
   - Đăng nhập bằng tài khoản editor được cấp.
   - Nghe thử âm thanh và tải về master export (xác nhận chỉ dùng Bearer header, không query token).
   - Thanh tiến trình tổng hợp cập nhật mượt qua SSE không bị trễ.

---

## 3. TIÊU CHÍ KÍCH HOẠT HỦY BỎ (ROLLBACK TRIGGERS)

Lập tức thực hiện quy trình hủy bỏ khẩn cấp nếu phát hiện bất kỳ dấu hiệu nào sau đây:
1. Phát hiện gói tin HTTP không mã hóa lọt ra ngoài mạng LAN.
2. Cảnh báo an ninh tường lửa hoặc kết nối từ địa chỉ IP ngoài dải mạng LAN cho phép.
3. Tỷ lệ lỗi rate limiting tăng đột biến (nhầm lẫn giữa các client khác nhau).
4. Độ trễ phản hồi SSE hoặc Audio Streaming vượt quá 200ms gây gián đoạn công việc biên tập.
5. Xung đột tiến trình khiến FastAPI hoặc Caddy bị dừng đột ngột.

---

## 4. QUY TRÌNH HỦY BỎ KHẨN CẤP TRONG 60 GIÂY (EMERGENCY ROLLBACK)

Khi có lệnh hủy bỏ, thực hiện ngay lập tức 3 bước sau:

### Bước 1: Dừng tiến trình Caddy Reverse Proxy
```powershell
Stop-Process -Name caddy -Force -ErrorAction SilentlyContinue
```

### Bước 2: Xóa ngay lập tức luật tường lửa Windows đã tạo
```powershell
Remove-NetFirewallRule -DisplayName "AI Voice Studio HTTPS Gateway" -ErrorAction SilentlyContinue
```

### Bước 3: Khôi phục Caddyfile về chế độ Loopback 5B-1
Khôi phục binding trong `infra/caddy/Caddyfile` về:
```caddyfile
https://127.0.0.1:9443 {
    tls internal
    # ...
}
```

### Bước 4: Kiểm tra lại an ninh mạng
Chạy lệnh kiểm tra cổng từ máy khác trong mạng LAN:
```powershell
Test-NetConnection -ComputerName 192.168.1.15 -Port 9443
```
*Kết quả kỳ vọng:* `TcpTestSucceeded: False` (Cổng đã đóng hoàn toàn với mạng LAN).  
Hệ thống AI Voice Studio được đảm bảo an toàn tuyệt đối trở lại trong ranh giới loopback `127.0.0.1`.
