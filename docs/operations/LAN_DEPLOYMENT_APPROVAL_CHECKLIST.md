# AI VOICE STUDIO — BẢNG KIỂM PHÊ DUYỆT KÍCH HOẠT MẠNG CỤC BỘ (LAN)
## LAN DEPLOYMENT APPROVAL CHECKLIST & OPERATIONAL GATE

> [!CAUTION]
> **VĂN BẢN QUẢN TRỊ DỰ ÁN — CẦN CHỮ KÝ PHÊ DUYỆT CỦA PRODUCT OWNER**  
> Việc kích hoạt mạng LAN và mở cổng tường lửa Windows **CHƯA ĐƯỢC CẤP PHÉP**.  
> Tài liệu này phân định rạch ròi giữa **Cấu hình Đã Dàn dựng (Staged)** và **Triển khai Thực tế Đã Kiểm thử (Tested Real LAN)**.  
> Chỉ được phép kích hoạt sau khi tất cả các mục kiểm tra trong văn bản này được ký xác nhận bởi các bên liên quan.

---

## 1. THÔNG SỐ TRIỂN KHAI MẠNG LAN CỤC BỘ ĐƯỢC PHÊ DUYỆT

| Tham số kỹ thuật | Giá trị cấu hình đề xuất | Giá trị phê duyệt thực tế | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Workstation Hostname** | `studio-server.local` | *(Điền tên máy trạm thực tế — không suy đoán)* | [ ] Chưa duyệt |
| **Static LAN IP** | `192.168.1.50` | *(Điền IP cố định máy trạm — không suy đoán)* | [ ] Chưa duyệt |
| **Allowed Client Subnet** | `192.168.1.0/24` | *(Dải mạng phòng thu được cấp phép)* | [ ] Chưa duyệt |
| **Gateway Port** | `9443` (TCP HTTPS Only) | `9443` (TCP HTTPS Only) | [ ] Chưa duyệt |
| **Root CA SPKI Fingerprint**| *(Trích xuất từ root.crt)*| *(Bắt buộc đối soát trên máy khách)* | [ ] Chưa duyệt |
| **HTTP Port 8080** | **ĐÓNG (DISABLED)** | **ĐÓNG (DISABLED)** | [x] Đã khóa |
| **Network Profile** | **Private Network duy nhất** | Private Network | [ ] Chưa duyệt |

---

## 2. KẾ HOẠCH PHÂN PHỐI CHỨNG CHỈ ROOT CA (ROOT CA DISTRIBUTION PLAN)

- [ ] **Bảo vệ Root CA gốc:** Caddy chạy với `skip_install_trust`, không tự cài đặt CA vào Windows Certificate Store của máy chủ phòng thu.
- [ ] **Trích xuất chứng chỉ công khai:** File công khai `root.crt` tại `$env:LOCALAPPDATA\Caddy\pki\authorities\local\root.crt` được sao chép an toàn qua kênh nội bộ (USB/chia sẻ nội bộ có xác thực), **tuyệt đối không sao chép khóa bí mật `root.key`**.
- [ ] **Cài đặt trên máy khách biên tập (Client Machine):**
  - Thực thi lệnh nhập chứng chỉ tin cậy trên từng máy khách được ủy quyền:
    ```powershell
    certutil -addstore -f "Root" root.crt
    ```
  - Xác nhận trình duyệt (Chrome/Edge) trên máy khách nhận diện chứng chỉ hợp lệ và không hiển thị màn hình cảnh báo đỏ.

---

## 3. QUY TRÌNH KIỂM THỬ THỰC TẾ TRÊN 2 MÁY TÍNH VẬT LÝ (2-MACHINE ACCEPTANCE)

> [!IMPORTANT]
> Toàn bộ thử nghiệm trước đây chỉ mới thực hiện trên loopback `127.0.0.1`. Bước này là **BẮT BUỘC** trên 2 máy tính vật lý riêng biệt cùng kết nối vào mạng LAN phòng thu.

- [ ] **Bước 1: Bắt tay TLS & Chứng chỉ (TLS Handshake & SAN Verification):**
  - Máy khách B kết nối tới `https://192.168.1.50:9443` và `https://studio-server.local:9443`.
  - Xác nhận bắt tay TLS 1.3 thành công, chứng chỉ hiển thị đúng SAN IP/Hostname.
- [ ] **Bước 2: Xác thực & Phân quyền (Authentication & RBAC Acceptance):**
  - Đăng nhập tài khoản `editor` từ máy B.
  - Xác nhận token Bearer được lưu trữ an toàn trong browser state, không bị lộ trên thanh URL.
- [ ] **Bước 3: Dòng âm thanh & Xuất bản Master (Audio Journey Acceptance):**
  - Thực hiện nghe thử âm thanh (Audio Preview) qua stream Blob xác thực trên máy B.
  - Xuất bản Master DSP WAV (48kHz) và MP3 (320kbps).
  - Tải file Master về máy B, kiểm tra phát âm thanh cục bộ bình thường.
- [ ] **Bước 4: Luồng thời gian thực không đệm (SSE Real-Time Progress):**
  - Gửi tác vụ tạo âm thanh và quan sát thanh tiến trình cập nhật thời gian thực trên máy B.
  - Xác nhận không bị hiện tượng đệm (buffering stall) qua mạng Wi-Fi/Ethernet.
- [ ] **Bước 5: Kiểm tra Từ chối Mạng Lạ (Subnet ACL Rejection):**
  - Thử nghiệm kết nối từ một địa chỉ IP ngoài dải `STUDIO_APPROVED_SUBNET` (nếu có giả lập) -> nhận mã `403 Forbidden` ngay lập tức.

---

## 4. GIỚI HẠN TÀI NGUYÊN VÀ CÂN BẰNG TẢI (RESOURCE LIMITS)

- [ ] **Hạn ngạch dung lượng lưu trữ:** Mỗi biên tập viên giới hạn `5,120 MB` (5 GB) dung lượng lưu trữ audio artifacts.
- [ ] **Hàng đợi tác vụ công bằng (Fair-Share Scheduling):** Tối đa `25` tác vụ chờ/đang chạy cho mỗi người dùng; thuật toán luân phiên công bằng Round-Robin ngăn chặn độc chiếm tài nguyên.
- [ ] **Giới hạn luồng CPU Inference:** Giữ nguyên `MAX_CONCURRENT_CPU_JOBS = 1` để đảm bảo độ ổn định và nhiệt độ máy trạm xử lý.

---

## 5. HƯỚNG DẪN DỪNG KHẨN CẤP VÀ HỦY BỎ CHỈ Ở CỔNG MẠNG (GATEWAY-ONLY ROLLBACK)

Nếu phát hiện bất kỳ dấu hiệu bất thường nào trong quá trình vận hành LAN:

```powershell
# 1. DỪNG TIẾN TRÌNH CADDY LAN THEO ĐÚNG PID QUẢN LÝ:
if (Test-Path "infra\caddy\caddy_lan.pid") {
    $caddyPid = (Get-Content "infra\caddy\caddy_lan.pid").Trim()
    if ($caddyPid) { Stop-Process -Id ([int]$caddyPid) -Force -ErrorAction SilentlyContinue }
    Remove-Item "infra\caddy\caddy_lan.pid" -Force -ErrorAction SilentlyContinue
}

# 2. XÓA ĐÚNG LUẬT TƯỜNG LỬA ĐỊNH DANH DUY NHẤT:
Remove-NetFirewallRule -Name "AIVoiceStudio_LAN_Gateway_TCP_9443" -ErrorAction SilentlyContinue

# 3. TRẢ CẤU HÌNH VỀ LOOPBACK CHO MÁY TRẠM:
.\infra\caddy\caddy.exe run --config "infra\caddy\Caddyfile"
```

> [!CAUTION]
> **CẢNH BÁO QUAN TRỌNG:**  
> Lệnh dừng khẩn cấp và Rollback mạng **KHÔNG ĐƯỢC CHẠM VÀO DATABASE `studio.db` HAY FILE ÂM THANH**. Dữ liệu đang làm việc của người dùng được bảo tồn 100%.

---

## 6. PHẦN KÝ DUYỆT CỦA CÁC BÊN LIÊN QUAN

| Vai trò | Họ tên | Chữ ký / Xác nhận | Ngày ký |
| :--- | :--- | :--- | :--- |
| **Product Owner** | | `[ ] PHÊ DUYỆT  [ ] TỪ CHỐI` | |
| **Principal Security Architect** | | `[ ] ĐẠT TIÊU CHUẨN AN NINH` | |
| **Windows Deployment Engineer** | | `[ ] ĐÃ SẴN SÀNG HẠ TẦNG` | |
