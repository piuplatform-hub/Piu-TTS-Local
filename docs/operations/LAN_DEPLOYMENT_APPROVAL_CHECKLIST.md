# AI VOICE STUDIO — BẢNG KIỂM PHÊ DUYỆT KÍCH HOẠT MẠNG CỤC BỘ (LAN)
## LAN DEPLOYMENT APPROVAL CHECKLIST & TWO-GATE OPERATIONAL CONTROL

> [!CAUTION]
> **VĂN BẢN QUẢN TRỊ DỰ ÁN — PHÂN ĐỊNH HAI CỔNG DUYỆT (GATE A & GATE B)**  
> 1. **Trước Gate A:** Cổng tường lửa Windows **CHƯA ĐƯỢC MỞ**, binding ra ngoài loopback **BỊ CẤM TUYỆT ĐỐI**.  
> 2. **Gate A (Thử nghiệm 2 máy có thời hạn):** Product Owner chỉ cấp phép mở cổng có kiểm soát cho một phiên kiểm thử trên 2 máy tính vật lý.  
> 3. **Gate B (Vận hành LAN thường xuyên):** Chỉ được xem xét sau khi Biên bản nghiệm thu 2 máy (Gate A) đạt 100% PASS.

---

## 1. THÔNG SỐ TRIỂN KHAI MẠNG LAN CỤC BỘ ĐƯỢC XÁC THỰC THỰC TẾ

| Tham số kỹ thuật | Giá trị xác thực trên máy chủ | Giá trị phê duyệt thực tế | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Workstation Hostname** | `88DB120531F23C4.local` *(mDNS)* | `88DB120531F23C4.local` | [ ] Chờ duyệt Gate A |
| **Active LAN Interface IP** | `192.168.1.73` *(Interface: Ethernet)*| `192.168.1.73` | [ ] Chờ duyệt Gate A |
| **Approved Client Subnet** | `192.168.1.0/24` *(Prefix /24)* | `192.168.1.0/24` | [ ] Chờ duyệt Gate A |
| **Gateway Port** | `9443` (TCP HTTPS Only) | `9443` (TCP HTTPS Only) | [ ] Chờ duyệt Gate A |
| **HTTP Port 8080** | **ĐÓNG HOÀN TOÀN (DISABLED)** | **ĐÓNG HOÀN TOÀN** | [x] Đã khóa |
| **Caddy Root CA File** | `%APPDATA%\caddy\pki\authorities\local\root.crt` | Xác thực tệp tồn tại | [x] Đã đối soát |
| **Root CA SHA-256 Hash**| `c0294d0dc75a3ef3eef911b842ee0072b0cf19b5829740695d22ff3018199a79` | Khớp tệp chứng chỉ | [x] Đã xác minh |
| **Root CA SPKI (Pinning)**| `LGk3TRqlmtCLTZui1dPvMdlWy9TqBrjYi9qo8qej8lI=` | Khóa công khai CA | [ ] Đối soát máy B |
| **Network Profile** | **Private Network duy nhất** | Private Network | [ ] Chờ duyệt Gate A |

---

## 2. KẾ HOẠCH PHÂN PHỐI CHỨNG CHỈ ROOT CA (ROOT CA DISTRIBUTION PLAN)

- [ ] **Bảo vệ Root CA gốc:** Caddy chạy với `skip_install_trust`, không tự cài đặt CA vào Windows Certificate Store của máy chủ phòng thu.
- [ ] **Trích xuất chứng chỉ công khai:** File công khai `root.crt` tại `$env:APPDATA\caddy\pki\authorities\local\root.crt` được sao chép qua kênh nội bộ (USB/kênh chia sẻ an toàn), **tuyệt đối không sao chép khóa bí mật `root.key`**.
- [ ] **Cài đặt trên máy khách biên tập (Client Machine):**
  - Thực thi lệnh nhập chứng chỉ tin cậy trên máy khách được ủy quyền:
    ```powershell
    certutil -addstore -f "Root" root.crt
    ```
  - Xác nhận trình duyệt (Chrome/Edge) trên máy khách nhận diện chứng chỉ hợp lệ và không hiển thị màn hình cảnh báo đỏ.

---

## 3. QUY TRÌNH KIỂM THỬ THỰC TẾ TRÊN 2 MÁY TÍNH VẬT LÝ (GATE A ACCEPTANCE)

> [!IMPORTANT]
> Toàn bộ thử nghiệm trước đây chỉ mới thực hiện trên loopback `127.0.0.1`. Bước này là **BẮT BUỘC** trên 2 máy tính vật lý riêng biệt cùng kết nối vào mạng LAN phòng thu sau khi có phê duyệt Gate A.

- [ ] **Bước 1: Bắt tay TLS & Chứng chỉ (TLS Handshake & SAN Verification):**
  - Máy khách B kết nối tới `https://192.168.1.73:9443` và `https://88DB120531F23C4.local:9443`.
  - Xác nhận bắt tay TLS 1.3 thành công, chứng chỉ hiển thị đúng SAN IP/Hostname.
- [ ] **Bước 2: Xác thực & Phân quyền (Authentication & RBAC Acceptance):**
  - Đăng nhập bằng tài khoản thử nghiệm được phân quyền (ví dụ: `editor`).
  - Xác nhận token Bearer được lưu trữ an toàn trong browser state, không lộ trên thanh URL.
- [ ] **Bước 3: Dòng âm thanh & Xuất bản Master (Audio Journey Acceptance):**
  - Thực hiện nghe thử âm thanh (Audio Preview) qua stream Blob xác thực trên máy B.
  - Xuất bản Master DSP WAV (48kHz) và MP3 (320kbps).
  - Tải file Master về máy B, kiểm tra phát âm thanh cục bộ bình thường.
- [ ] **Bước 4: Luồng thời gian thực không đệm (SSE Real-Time Progress):**
  - Gửi tác vụ tạo âm thanh và quan sát thanh tiến trình cập nhật thời gian thực trên máy B.
  - Xác nhận không bị hiện tượng đệm (buffering stall) qua mạng Wi-Fi/Ethernet.
- [ ] **Bước 5: Kiểm tra Từ chối Mạng Lạ (Subnet ACL Rejection):**
  - Thử nghiệm kết nối từ một địa chỉ IP ngoài dải `192.168.1.0/24` (nếu có giả lập) -> nhận mã `403 Forbidden` ngay lập tức.

---

## 4. GIỚI HẠN TÀI NGUYÊN VÀ CÂN BẰNG TẢI (RESOURCE LIMITS)

- [ ] **Hạn ngạch dung lượng lưu trữ:** Mỗi biên tập viên giới hạn `5,120 MB` (5 GB) dung lượng lưu trữ audio artifacts.
- [ ] **Hàng đợi tác vụ công bằng (Fair-Share Scheduling):** Tối đa `25` tác vụ chờ/đang chạy cho mỗi người dùng; thuật toán luân phiên công bằng Round-Robin ngăn chặn độc chiếm tài nguyên.
- [ ] **Giới hạn luồng CPU Inference:** Giữ nguyên `MAX_CONCURRENT_CPU_JOBS = 1` để đảm bảo độ ổn định và nhiệt độ máy trạm xử lý.

---

## 5. HƯỚNG DẪN DỪNG KHẨN CẤP VÀ HỦY BỎ CỔNG MẠNG CÓ ĐỐI SOÁT (SCOPED ROLLBACK)

Nếu phát hiện bất kỳ dấu hiệu bất thường nào trong quá trình vận hành LAN:

```powershell
# Chạy script hủy bỏ có kiểm soát (không tắt nhầm tiến trình, không xóa nhầm rule tường lửa):
powershell -ExecutionPolicy Bypass -File scripts\lan_rollback.ps1
```

> [!CAUTION]
> **CẢNH BÁO QUAN TRỌNG:**  
> Lệnh dừng khẩn cấp và Rollback mạng **TUYỆT ĐỐI KHÔNG ĐƯỢC CHẠM VÀO DATABASE `studio.db` HAY FILE ÂM THANH**. Dữ liệu đang làm việc của người dùng được bảo tồn 100%.

---

## 6. PHẦN KÝ DUYỆT THEO HAI CỔNG QUẢN TRỊ (TWO-GATE SIGN-OFF)

### CỔNG A: PHÊ DUYỆT THỬ NGHIỆM THỰC TẾ TRÊN 2 MÁY (GATE A — PILOT TESTING AUTHORIZATION)
*Cấp phép tạm thời mở cổng 9443 trên IP `192.168.1.73`, subnet `192.168.1.0/24` phục vụ phiên kiểm thử 2 máy vật lý có giám sát.*

| Vai trò | Họ tên | Ý kiến / Quyết định | Ngày ký |
| :--- | :--- | :--- | :--- |
| **Product Owner** | | `[ ] CẤP PHÉP GATE A   [ ] TỪ CHỐI` | |
| **Principal Security Architect** | | `[ ] ĐẠT YÊU CẦU THỬ NGHIỆM` | |
| **Windows Deployment Engineer** | | `[ ] SẴN SÀNG GIÁM SÁT THỬ NGHIỆM`| |

---

### CỔNG B: PHÊ DUYỆT VẬN HÀNH LAN THƯỜNG XUYÊN (GATE B — ROUTINE LAN OPERATION)
*Chỉ được ký sau khi toàn bộ 5 bước tại Mục 3 (Gate A Acceptance) được đánh dấu hoàn thành 100%.*

| Vai trò | Họ tên | Ý kiến / Quyết định | Ngày ký |
| :--- | :--- | :--- | :--- |
| **Product Owner** | | `[ ] CẤP PHÉP GATE B   [ ] TỪ CHỐI` | |
| **Principal Security Architect** | | `[ ] ĐẠT TIÊU CHUẨN VẬN HÀNH`| |
| **Windows Deployment Engineer** | | `[ ] SẴN SÀNG CHUYỂN GIAO` | |
