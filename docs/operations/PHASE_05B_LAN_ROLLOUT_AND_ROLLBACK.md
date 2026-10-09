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
- [ ] Quản trị viên phòng thu và Product Owner đã ký duyệt ủy quyền mở cổng LAN bằng văn bản trên [LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md](file:///d:/C/Dev/du%20an/TTS/docs/operations/LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md).
- [ ] Máy trạm Windows đang kết nối vào profile mạng **Private Network** (không áp dụng cho Public Network).
- [ ] Địa chỉ IP máy trạm (`LAN_IP`), tên miền nội bộ (`LAN_HOSTNAME`), cổng HTTPS (`LAN_PORT`) và dải mạng cho phép (`STUDIO_APPROVED_SUBNET`) đã được định danh và xác thực cụ thể, không dùng giá trị mặc định phỏng đoán.

---

## 2. QUY TRÌNH TRIỂN KHAI MẠNG LAN CÓ KIỂM SOÁT (ROLLOUT PROCEDURE)

### Bước 1: Xác định địa chỉ IP mạng LAN và Subnet được phê duyệt
Mở PowerShell và chạy lệnh:
```powershell
Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*", "Wi-Fi*" | 
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | 
    Select-Object IPAddress, InterfaceAlias, PrefixLength
```
*Ví dụ thông số phê duyệt: IP `192.168.1.50`, Subnet `192.168.1.0/24`, Hostname `studio-server.local`, Cổng `9443`.*

### Bước 2: Thiết lập Tường lửa Windows Định danh Duy nhất (Scoped Firewall Rule)
Tạo luật tường lửa với Name định danh duy nhất `AIVoiceStudio_LAN_Gateway_TCP_9443`:
```powershell
# Chạy với quyền Administrator
New-NetFirewallRule -Name "AIVoiceStudio_LAN_Gateway_TCP_9443" `
    -DisplayName "AI Voice Studio LAN HTTPS Gateway (Port 9443)" `
    -Direction Inbound `
    -LocalPort 9443 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private `
    -Description "Dedicated reverse proxy HTTPS inbound access for Studio editors (Phase 5B-2)"
```
*Lưu ý: Tuyệt đối KHÔNG mở cổng HTTP 8080 trong đợt triển khai.*

### Bước 3: Áp dụng Cấu hình Caddyfile LAN và Lưu vết Tiến trình (Process Tracking)
Khởi chạy Caddy với các biến môi trường tường minh và ghi lại Process ID (PID):
```powershell
$env:LAN_IP = "192.168.1.50"
$env:LAN_HOSTNAME = "studio-server.local"
$env:STUDIO_APPROVED_SUBNET = "192.168.1.0/24"
$env:LAN_PORT = "9443"
$env:BACKEND_PORT = "8765"

# 1. Thẩm định cú pháp cấu hình trước khi chạy
.\infra\caddy\caddy.exe validate --config "infra\caddy\Caddyfile.lan.template"

# 2. Khởi chạy Caddy tiến trình nền có theo dõi PID
$caddyProc = Start-Process -FilePath ".\infra\caddy\caddy.exe" `
    -ArgumentList "run --config infra\caddy\Caddyfile.lan.template" `
    -PassThru

# 3. Ghi PID vào file quản lý phiên triển khai
$caddyProc.Id | Out-File -FilePath "infra\caddy\caddy_lan.pid" -Encoding ascii
Write-Host "Caddy LAN Gateway started with controlled PID: $($caddyProc.Id)"
```

### Bước 4: Phân phối Chứng chỉ Root CA tới Máy Khách Biên Tập Viên
1. Trích xuất file Root CA công khai từ máy chủ phòng thu:
   `$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt`
2. Phân phối file `root.crt` tới các máy tính biên tập viên được ủy quyền trong mạng LAN (tuyệt đối không sao chép `root.key`).
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

Thực hiện tuần tự các bước sau:

### Bước 1: Dừng Chính Xác Tiến trình Caddy Được Quản lý (Scoped PID Termination)
Chỉ dừng đúng tiến trình Caddy thuộc phiên triển khai LAN, không quét tắt tiến trình ngoài phạm vi:
```powershell
if (Test-Path "infra\caddy\caddy_lan.pid") {
    $caddyPid = (Get-Content "infra\caddy\caddy_lan.pid").Trim()
    if ($caddyPid -match '^\d+$') {
        Stop-Process -Id ([int]$caddyPid) -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Caddy LAN process PID: $caddyPid"
    }
    Remove-Item "infra\caddy\caddy_lan.pid" -Force -ErrorAction SilentlyContinue
} else {
    # Dự phòng an toàn: Chỉ dừng Caddy có commandline chứa template LAN
    Get-CimInstance Win32_Process -Filter "Name = 'caddy.exe'" | 
        Where-Object { $_.CommandLine -like "*Caddyfile.lan*" } | 
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

# Kiểm tra giải phóng cổng 9443
Get-NetTCPConnection -LocalPort 9443 -ErrorAction SilentlyContinue
```

### Bước 2: Xóa Chính Xác Luật Tường Lửa Định Danh Duy nhất
Chỉ xóa đúng rule `AIVoiceStudio_LAN_Gateway_TCP_9443`, bảo tồn toàn bộ các cấu hình tường lửa khác trên máy chủ:
```powershell
Remove-NetFirewallRule -Name "AIVoiceStudio_LAN_Gateway_TCP_9443" -ErrorAction SilentlyContinue
Write-Host "Firewall rule AIVoiceStudio_LAN_Gateway_TCP_9443 removed."
```

### Bước 3: Phục hồi Gateway về Cấu hình Loopback Staging An toàn
Khởi động lại Caddy với cấu hình loopback gốc [infra/caddy/Caddyfile](file:///d:/C/Dev/du%20an/TTS/infra/caddy/Caddyfile) (`127.0.0.1:9443`):
```powershell
# Giữ nguyên Caddy v2.11.7 (chỉ hạ cấp nếu có lỗi tương thích binary được ghi nhận)
.\infra\caddy\caddy.exe run --config "infra\caddy\Caddyfile"
```

### Bước 4: Xác minh Cô lập Dịch vụ (Service Isolation Verification)
1. **Kiểm tra từ máy tính khác trong mạng LAN:**
   ```powershell
   Test-NetConnection -ComputerName 192.168.1.50 -Port 9443
   ```
   *Kết quả kỳ vọng:* `TcpTestSucceeded: False` (Cổng 9443 đã đóng hoàn toàn đối với mạng ngoài).
2. **Kiểm tra từ máy trạm cục bộ:**
   Truy cập `https://127.0.0.1:9443` hoạt động bình thường, dữ liệu dự án và kho âm thanh hoàn toàn nguyên vẹn.

---

## 5. QUY TRÌNH B: PHỤC HỒI THẢM HỌA DỮ LIỆU (DISASTER RECOVERY PROCEDURE)

> [!CAUTION]
> **QUY TRÌNH CÓ ĐIỀU KIỆN ĐẶC BIỆT — CHỈ THỰC HIỆN KHI CÓ PHÊ DUYỆT BẰNG VĂN BẢN**  
> Quy trình này CHỈ được kích hoạt khi phát hiện cơ sở dữ liệu SQLite bị hỏng vật lý (`database disk image is malformed`) hoặc thảm họa phần cứng không thể phục hồi.  
> **NGHIÊM CẤM** tự ý ghi đè dữ liệu production trong các sự cố mạng hoặc cấu hình gateway.

### Bước 1: Phê duyệt Tường minh từ Product Owner & Đánh giá Cửa sổ Mất mát Dữ liệu
- Lập biên bản sự cố, xác định nguyên nhân hỏng hóc vật lý.
- Xác định điểm khôi phục mục tiêu (RPO - Recovery Point Objective): Bản sao lưu `studio_db_online_backup_verified` gần nhất.
- **Xác định Cửa sổ Mất mát Dữ liệu (Data Loss Window):** Toàn bộ dữ liệu dự án, kịch bản tạo ra sau thời điểm sao lưu sẽ bị mất. Cần thông báo cho biên tập viên trước khi thực hiện.
- Nhận phê duyệt bằng văn bản từ Product Owner.

### Bước 2: Dừng Toàn bộ Luồng Ghi Dữ liệu (Stop All SQLite Writers)
Trước khi thao tác với file SQLite, BẮT BUỘC phải dừng toàn bộ tiến trình có kết nối mở tới cơ sở dữ liệu:
```powershell
# Dừng backend FastAPI / Uvicorn và toàn bộ Worker engines
Get-CimInstance Win32_Process | 
    Where-Object { 
        $_.CommandLine -like "*apps.server.src*" -or 
        $_.CommandLine -like "*engines\*worker.py*" 
    } | 
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "All backend SQLite writer processes stopped."
```

### Bước 3: Khôi phục Thử nghiệm vào Môi trường Cách ly (Disposable Sandbox)
Trước khi chạm vào dữ liệu production, BẮT BUỘC phải kiểm tra bản sao lưu trong thư mục sandbox tạm thời:
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
assert cur.fetchone()[0] == 'ok', 'Integrity check failed'
cur.execute('PRAGMA foreign_key_check')
assert len(cur.fetchall()) == 0, 'FK check failed'
cur.execute('SELECT COUNT(*) FROM users')
print('Sandbox restored users count:', cur.fetchone()[0])
conn.close()
"
```
*Chỉ tiếp tục khi `PRAGMA integrity_check` trả về `ok` và foreign key check sạch.*

### Bước 4: Lưu trữ Bản Chụp Hiện Trường & Dọn dẹp File WAL Cũ (Forensic Quarantine)
Di dời toàn bộ bộ ba `studio.db`, `studio.db-wal`, `studio.db-shm` sang thư mục cách ly để tránh xung đột ghi đè trang WAL cũ:
```powershell
$quarantineDir = "D:\AIVoiceStudioData\backups\damaged_quarantine_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $quarantineDir

# Di chuyển toàn bộ file DB và WAL hiện tại vào vùng cách ly
Move-Item "D:\AIVoiceStudioData\studio.db*" $quarantineDir -Force
Write-Host "Damaged DB and WAL files moved to quarantine: $quarantineDir"
```

### Bước 5: Thực hiện Thay thế File Dữ liệu Production & Điều phối Hệ thống Tệp
1. **Khôi phục SQLite:**
   ```powershell
   Copy-Item "D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db" "D:\AIVoiceStudioData\studio.db" -Force
   ```
2. **Đối soát Hệ thống Tệp Âm thanh (Audio Filesystem Reconciliation):**
   - Rà soát các tệp trong `D:\AIVoiceStudioData\artifacts\` và `projects\`.
   - Các file âm thanh sinh ra sau thời điểm sao lưu (không có trong DB đã khôi phục) được chuyển vào `D:\AIVoiceStudioData\orphaned_audio/` để phục vụ biên tập viên trích xuất thủ công nếu cần.
3. **Khởi động lại backend và thẩm định hoạt động:**
   ```powershell
   # Khởi động lại server và kiểm tra API health
   .venv\Scripts\python.exe -m apps.server.src.main
   ```

---

## 6. PHÂN ĐỊNH RÕ RÀNG VỀ NĂNG LỰC PHỤC HỒI DỮ LIỆU (RECOVERY REALITY)

| Cấp độ bảo vệ | Phạm vi dữ liệu | Khả năng phục hồi hiện tại | Ghi chú an toàn |
| :--- | :--- | :---: | :--- |
| **Verified Database Backup** | File SQLite metadata (`studio.db`) | **ĐÃ KIỂM CHỨNG (100% OK)** | Đã kiểm chứng SHA-256, `PRAGMA integrity_check` và FK check. |
| **Verified Filesystem Backup** | Tệp âm thanh (`artifacts`, `projects`, `exports`) | **CHƯA ĐƯỢC TỰ ĐỘNG HÓA** | Hiện lưu trữ trên ổ đĩa vật lý, chưa có snapshot đồng bộ thời điểm. |
| **Consistent Application-Wide Recovery Point** | Đồng bộ tuyệt đối cả Database & Filesystem | **THEO CỬA SỔ SAO LƯU (RPO Window)** | Dữ liệu sinh ra giữa 2 lần sao lưu chấp nhận mất mát nếu phục hồi. |
| **Proposed Future Full Backup Implementation** | Sao lưu trọn gói DB + FS + SHA-256 Manifest | **ĐÃ THIẾT KẾ KIẾN TRÚC** | Đã hoàn thiện thiết kế trong tài liệu [COMPREHENSIVE_BACKUP_AND_DISASTER_RECOVERY_DESIGN.md](file:///d:/C/Dev/du%20an/TTS/docs/architecture/COMPREHENSIVE_BACKUP_AND_DISASTER_RECOVERY_DESIGN.md). |
