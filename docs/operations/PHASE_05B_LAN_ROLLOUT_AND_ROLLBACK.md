# AI Voice Studio — Milestone 5B-2: LAN Rollout & Non-Destructive Rollback Runbook

> [!CAUTION]
> **TÀI LIỆU QUY TRÌNH CHƯA THỰC THI (UNEXECUTED PROCEDURES)**  
> Bản hướng dẫn này được chuẩn bị phục vụ việc kích hoạt mạng LAN có kiểm soát (Milestone 5B-2).  
> **HIỆN TẠI: CHƯA ĐƯỢC PHÉP THỰC THI (NOT AUTHORIZED)**. Tuyệt đối không tự ý mở cổng tường lửa hay thay đổi binding IP sang IP mạng LAN cho đến khi có sự phê chuẩn chính thức bằng văn bản của Product Owner.

---

## 1. MỤC TIÊU VÀ ĐIỀU KIỆN TIÊN QUYẾT (PRE-ROLLOUT CHECKLIST)

Chỉ bắt đầu triển khai Milestone 5B-2 khi thỏa mãn 100% các điều kiện sau:
- [ ] Milestone 5B-1 đã được nghiệm thu hoàn tất với 100% ca kiểm thử tự động PASS (132/132 Pytest tests).
- [ ] Tệp thực thi Caddy v2.11.7 đã được xác minh toàn vẹn SHA-512 chính thức.
- [ ] Đã thực hiện sao lưu trực tuyến cơ sở dữ liệu (`studio_db_online_backup_verified`) và xác minh SHA-256 thành công.
- [ ] Quản trị viên phòng thu và Product Owner đã ký duyệt ủy quyền mở cổng LAN bằng văn bản.
- [ ] Máy trạm Windows đang kết nối vào profile mạng **Private Network** (không áp dụng cho Public Network).
- [ ] Địa chỉ IP máy trạm (`LAN_IP`), tên miền nội bộ (`LAN_HOSTNAME`) và dải mạng cho phép (`STUDIO_APPROVED_SUBNET`) đã được định danh cụ thể.

---

## 2. QUY TRÌNH TRIỂN KHAI MẠNG LAN CÓ KIỂM SOÁT (ROLLOUT PROCEDURE)

### Bước 1: Xác định địa chỉ IP mạng LAN và Subnet được phê duyệt
Mở PowerShell và chạy lệnh:
```powershell
Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*", "Wi-Fi*" | 
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | 
    Select-Object IPAddress, InterfaceAlias, PrefixLength
```
*Ví dụ IP xác định được: `192.168.1.50`, Subnet phòng thu: `192.168.1.0/24`, Hostname: `studio-server.local`.*

### Bước 2: Thiết lập Tường lửa Windows (Windows Firewall Rule — Chỉ Cổng HTTPS 9443)
Chỉ mở duy nhất cổng 9443 TCP và giới hạn nghiêm ngặt trong phân vùng mạng Private:
```powershell
# Chạy với quyền Administrator
New-NetFirewallRule -DisplayName "AI Voice Studio LAN HTTPS Gateway (Port 9443)" `
    -Direction Inbound `
    -LocalPort 9443 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private `
    -Description "Reverse Proxy HTTPS inbound access for Studio editors"
```
*Lưu ý: Tuyệt đối KHÔNG mở cổng HTTP 8080 trong đợt triển khai ban đầu.*

### Bước 3: Áp dụng Cấu hình Caddyfile LAN Đã Thắt Chặt (Hardened Template)
Khởi chạy Caddy với các biến môi trường tường minh (sử dụng template [infra/caddy/Caddyfile.lan.template](file:///d:/C/Dev/du%20an/TTS/infra/caddy/Caddyfile.lan.template)):
```powershell
$env:LAN_IP = "192.168.1.50"
$env:LAN_HOSTNAME = "studio-server.local"
$env:STUDIO_APPROVED_SUBNET = "192.168.1.0/24"
$env:BACKEND_PORT = "8765"

# Kiểm tra cú pháp trước khi chạy
.\infra\caddy\caddy.exe validate --config "infra\caddy\Caddyfile.lan.template"

# Khởi chạy Caddy Gateway
.\infra\caddy\caddy.exe run --config "infra\caddy\Caddyfile.lan.template"
```

### Bước 4: Phân phối Chứng chỉ Root CA tới Máy Khách Biên Tập Viên
1. Trích xuất file Root CA từ máy chủ phòng thu:
   `$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt`
2. Phân phối file `root.crt` tới các máy tính biên tập viên được ủy quyền trong mạng LAN.
3. Trên máy tính khách (Windows), nhập chứng chỉ vào Trusted Root Store:
   ```powershell
   certutil -addstore -f "Root" root.crt
   ```

### Bước 5: Nghiệm thu Thực tế từ Máy Khách (2-Machine Acceptance Testing)
1. Trên máy chủ: FastAPI (`127.0.0.1:8765`) và Caddy (`192.168.1.50:9443`) đang hoạt động.
2. Từ máy tính khách trong cùng mạng LAN, mở trình duyệt truy cập:
   `https://192.168.1.50:9443` hoặc `https://studio-server.local:9443`
3. Xác minh:
   - Trình duyệt hiển thị biểu tượng ổ khóa bảo mật TLS hợp lệ (không cảnh báo đỏ).
   - Đăng nhập bằng tài khoản editor.
   - Nghe thử âm thanh (Audio Preview qua Blob) và tải Master Export WAV/MP3.
   - Luồng sự kiện tiến trình SSE cập nhật thời gian thực không bị trễ.

---

## 3. TIÊU CHÍ KÍCH HOẠT HỦY BỎ (ROLLBACK TRIGGERS)

Lập tức thực hiện quy trình hủy bỏ khẩn cấp nếu xuất hiện bất kỳ dấu hiệu nào sau đây:
1. Phát hiện kết nối từ địa chỉ IP nằm ngoài dải `STUDIO_APPROVED_SUBNET`.
2. Trình duyệt trên máy khách báo lỗi không thể thiết lập kết nối TLS hoặc timeout.
3. Tỷ lệ lỗi rate limiting tăng đột biến giữa các máy khách khác nhau.
4. Luồng SSE bị treo hoặc đệm (buffering) làm gián đoạn tiến trình biên tập âm thanh.
5. Sự cố tiến trình khiến Caddy hoặc Uvicorn bị dừng đột ngột.

---

## 4. QUY TRÌNH A: HỦY BỎ MẠNG & GATEWAY (PHI HỦY DIỆT DỮ LIỆU)

> [!IMPORTANT]
> **NGUYÊN TẮC BẢO TOÀN DỮ LIỆU TUYỆT ĐỐI (NON-DESTRUCTIVE ROLLBACK)**  
> Quy trình hủy bỏ Gateway/Mạng **TUYỆT ĐỐI KHÔNG BAO GIỜ tự động khôi phục hoặc ghi đè cơ sở dữ liệu `studio.db`**.  
> Toàn bộ dự án, kịch bản, bản thu âm thanh (`artifacts`, `exports`) và tài khoản người dùng hiện hành PHẢI ĐƯỢC GIỮ NGUYÊN VẸN 100%.

Thực hiện tuần tự 4 bước sau:

### Bước 1: Dừng tiến trình Caddy Reverse Proxy
```powershell
Get-Process -Name caddy -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Bước 2: Xóa ngay lập tức luật tường lửa Windows đã tạo
```powershell
Remove-NetFirewallRule -DisplayName "AI Voice Studio LAN HTTPS Gateway (Port 9443)" -ErrorAction SilentlyContinue
```

### Bước 3: Trả Gateway về Cấu hình Loopback Staging An Toàn
Khởi động lại Caddy với cấu hình staging loopback gốc [infra/caddy/Caddyfile](file:///d:/C/Dev/du%20an/TTS/infra/caddy/Caddyfile):
```powershell
.\infra\caddy\caddy.exe run --config "infra\caddy\Caddyfile"
```

### Bước 4: Xác minh Cô lập Dịch vụ (Service Isolation Verification)
1. Kiểm tra từ máy tính khác trong mạng LAN:
   ```powershell
   Test-NetConnection -ComputerName 192.168.1.50 -Port 9443
   ```
   *Kết quả kỳ vọng:* `TcpTestSucceeded: False` (Cổng 9443 đã đóng hoàn toàn đối với mạng ngoài).
2. Kiểm tra từ máy trạm cục bộ:
   Truy cập `https://127.0.0.1:9443` hoạt động bình thường, dữ liệu dự án và âm thanh hoàn toàn nguyên vẹn.

---

## 5. QUY TRÌNH B: PHỤC HỒI THẢM HỌA DỮ LIỆU (DISASTER RECOVERY PROCEDURE)

> [!CAUTION]
> **QUY TRÌNH CÓ ĐIỀU KIỆN ĐẶC BIỆT — CHỈ THỰC HIỆN KHI CÓ PHÊ DUYỆT BẰNG VĂN BẢN**  
> Quy trình này CHỈ được kích hoạt khi phát hiện cơ sở dữ liệu SQLite bị hỏng vật lý (`database disk image is malformed`) hoặc thảm họa phần cứng.  
> **NGHIÊM CẤM** tự ý ghi đè dữ liệu production trong các sự cố mạng hoặc cấu hình gateway.

### Bước 1: Phê duyệt Tường minh từ Product Owner
- Lập biên bản sự cố, xác định nguyên nhân hỏng hóc vật lý.
- Xác định điểm khôi phục mục tiêu (RPO - Recovery Point Objective): Bản sao lưu `studio_db_online_backup_verified` gần nhất.
- Xác định cửa sổ mất mát dữ liệu (Data Loss Window): Khoảng thời gian từ lúc tạo bản sao lưu đến thời điểm xảy ra sự cố.
- Nhận phê duyệt bằng văn bản từ Product Owner.

### Bước 2: Khôi phục Thử nghiệm vào Môi trường Cách ly (Disposable Sandbox)
Trước khi chạm vào dữ liệu production, BẮT BUỘC phải khôi phục thử nghiệm vào một thư mục tạm thời:
```powershell
$tempDir = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tempDir

# Sao chép bản sao lưu vào sandbox
Copy-Item "D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db" (Join-Path $tempDir "test_restore.db")

# Kiểm tra tính toàn vẹn và cấu trúc schema
python -c "
import sqlite3
conn = sqlite3.connect('$tempDir/test_restore.db')
cur = conn.cursor()
cur.execute('PRAGMA integrity_check')
print('Integrity Check:', cur.fetchall())
cur.execute('SELECT COUNT(*) FROM users')
print('Users count:', cur.fetchone()[0])
conn.close()
"
```
*Chỉ tiếp tục khi `PRAGMA integrity_check` trả về `ok` và số lượng bảng/bản ghi hợp lệ.*

### Bước 3: Lưu trữ Bản Chụp Hiện Trường (Forensic Preservation)
Lưu lại trạng thái file bị lỗi hiện tại trước khi thay thế:
```powershell
Copy-Item "D:\AIVoiceStudioData\studio.db" "D:\AIVoiceStudioData\backups\studio_damaged_snapshot.db" -Force
```

### Bước 4: Thực hiện Thay thế File Dữ liệu Production Có Kiểm Soát
```powershell
# Dừng hoàn toàn backend server
# Thay thế file database chính
Copy-Item "D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db" "D:\AIVoiceStudioData\studio.db" -Force

# Khởi động lại dịch vụ và thẩm định hoạt động
```
