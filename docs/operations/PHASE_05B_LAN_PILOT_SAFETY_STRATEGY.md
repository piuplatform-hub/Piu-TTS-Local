# AI VOICE STUDIO — CHIẾN LƯỢC BẢO VỆ DỮ LIỆU & QUẢN TRỊ LAN PILOT (PHASE 5B GATE A)
## DATA PROTECTION, CLIENT READINESS & ISOLATED PILOT RUNBOOK

---

### THÔNG TIN TÀI LIỆU & QUY CHUẨN
- **Dự án**: AI Voice Studio — Kiến trúc R1.1
- **Giai đoạn**: Phase 5B Gate A Readiness Check
- **Vai trò thực hiện**: Independent Security Auditor, SQLite Reliability Engineer & Release Manager
- **Trạng thái phê duyệt**: **CHƯA MỞ LAN (GATE A NOT AUTHORIZED)**

---

## 1. SO SÁNH VÀ LỰA CHỌN CHIẾN LƯỢC DỮ LIỆU THÍ ĐIỂM (PILOT STRATEGY)

Để bảo đảm an toàn tuyệt đối cho tài nguyên và dữ liệu đã nghiệm thu từ Phase 0 đến Phase 5A, hai chiến lược được xây dựng chi tiết:

| Tiêu chí | Phương án A — Thí điểm Cô lập (Option A: Isolated Pilot) *(Được chọn & Khuyến nghị)* | Phương án B — Thí điểm Production Có kiểm soát (Option B: Controlled Production Pilot) |
| :--- | :--- | :--- |
| **Cơ sở dữ liệu** | **Disposable SQLite database** (`pilot_sandbox\pilot_studio.db`) | Production database (`D:\AIVoiceStudioData\studio.db`) |
| **Thư mục âm thanh** | Thư mục riêng biệt (`pilot_sandbox\audio\`) | Thư mục chính (`D:\AIVoiceStudioData\audio\`) |
| **Rủi ro dữ liệu cũ** | **0% rủi ro** — Không có kết nối hoặc ghi đè vào dữ liệu cũ | Có rủi ro phát sinh bản ghi rác nếu test thất bại |
| **Tài khoản sử dụng** | Chỉ gồm `pilot_editor` và `acceptance_qa` | 13 QA accounts bị vô hiệu hóa; dùng `pilot_editor` |
| **Động cơ TTS** | Mock engine hoặc local engine độc lập | Local engine đầy đủ |
| **Yêu cầu phê duyệt** | Phê duyệt mở cổng thử nghiệm Cổng A của PO | Phê duyệt văn bản của PO kèm backup xác thực |
| **Quy trình Rollback** | Xóa thư mục tạm `pilot_sandbox`; tắt Caddy | Giữ nguyên DB; chỉ tắt Caddy & xóa rule tường lửa |

### Quyết định lựa chọn:
> [!IMPORTANT]
> **Hệ thống áp dụng Phương án A (Option A — Isolated Pilot)** làm chiến lược tiêu chuẩn cho Cổng A. Dữ liệu sản xuất `D:\AIVoiceStudioData\studio.db` và các tệp âm thanh hiện hữu được bảo vệ ở mức tối đa (Zero Write Handles). Phương án B chỉ kích hoạt khi Product Owner có yêu cầu bắt buộc bằng văn bản cần nghiệm thu trực tiếp trên các dự án hiện hữu.

---

## 2. QUY TRÌNH VẬN HÀNH PHƯƠNG ÁN A (ISOLATED PILOT RUNBOOK)

### 2.1. Chuẩn bị môi trường cô lập (Sandbox Setup)
1. Tạo thư mục cô lập:
   ```powershell
   New-Item -ItemType Directory -Path "D:\AIVoiceStudioData\pilot_sandbox\audio" -Force
   ```
2. Khởi tạo cơ sở dữ liệu tạm thời qua Alembic migrations:
   ```powershell
   $env:STUDIO_DATA_DIR = "D:\AIVoiceStudioData\pilot_sandbox"
   .venv\Scripts\python.exe -m alembic upgrade head
   ```
3. Cấp phát tài khoản `pilot_editor` trong cơ sở dữ liệu tạm thời:
   ```powershell
   .venv\Scripts\python.exe scripts/create_pilot_account.py --db-path "D:\AIVoiceStudioData\pilot_sandbox\studio.db" --execute
   ```
4. Cấu hình backend Uvicorn trỏ vào thư mục tạm thời:
   ```powershell
   $env:STUDIO_DATA_DIR = "D:\AIVoiceStudioData\pilot_sandbox"
   $env:STUDIO_DB_PATH = "D:\AIVoiceStudioData\pilot_sandbox\studio.db"
   ```

### 2.2. Dọn dẹp sau khi kết thúc Cổng A (Cleanup)
Sau khi hoàn tất kịch bản kiểm thử 2 máy:
1. Chạy `scripts/lan_rollback.ps1` để dừng Caddy LAN và đóng cổng tường lửa.
2. Dừng tiến trình Uvicorn sandbox.
3. Toàn bộ thư mục `D:\AIVoiceStudioData\pilot_sandbox` có thể lưu trữ để đối soát kiểm toán hoặc xóa bỏ hoàn toàn mà không để lại bất kỳ tác động nào tới dữ liệu chính.

---

## 3. QUY TRÌNH VẬN HÀNH PHƯƠNG ÁN B (CONTROLLED PRODUCTION PILOT RUNBOOK)

Trường hợp Product Owner phê duyệt kiểm thử trực tiếp trên dữ liệu chính:

### 3.1. Điều kiện tiên quyết trước khi mở cổng (Prerequisites)
1. **Xác thực bản sao lưu trực tuyến (Online SQLite Backup)**:
   ```powershell
   .venv\Scripts\python.exe scripts/create_verified_online_backup.py
   ```
   Kiểm tra mã băm SHA-256 và `PRAGMA integrity_check` đạt `ok`.
2. **Sao lưu thư mục tệp âm thanh (Audio Files Snapshot)**:
   ```powershell
   $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
   robocopy "D:\AIVoiceStudioData\audio" "D:\AIVoiceStudioData\backups\audio_$timestamp" /MIR /R:1 /W:1
   ```
3. **Thực thi vô hiệu hóa 13 tài khoản QA**:
   ```powershell
   sqlite3 "D:\AIVoiceStudioData\studio.db" < scripts/disable_qa_accounts.sql
   ```
4. **Cấp phát tài khoản `pilot_editor` trên cơ sở dữ liệu chính**:
   ```powershell
   .venv\Scripts\python.exe scripts/create_pilot_account.py --db-path "D:\AIVoiceStudioData\studio.db" --execute
   ```

### 3.2. RPO và RTO trong trường hợp sự cố (Recovery Objectives)
- **RPO (Recovery Point Objective)**: 0 giây (Nhờ SQLite WAL mode và bản snapshot trước phiên).
- **RTO (Recovery Time Objective)**: Dưới 5 phút (Khôi phục tệp DB và thư mục audio về trạng thái trước thử nghiệm).
- **Nguyên tắc bất di bất dịch**: Gateway rollback **KHÔNG BAO GIỜ** tự động ghi đè database; chỉ thực hiện khôi phục ngoại tuyến (Offline DR) khi có lệnh bằng văn bản của Product Owner.

---

## 4. BẢNG ĐỐI SOÁT CẤU HÌNH LAN & SỰ SẴN SÀNG CỦA MÁY KHÁCH (CLIENT READINESS)

| Thành phần kiểm soát | Tham số đã xác thực trên Máy chủ | Yêu cầu đối với Máy Khách B | Đánh giá an toàn |
| :--- | :--- | :--- | :---: |
| **Địa chỉ IP máy chủ** | `192.168.1.73` (Interface `Ethernet`) | Cùng dải mạng `192.168.1.0/24` | **SẴN SÀNG** |
| **DHCP / Static IP** | DHCP Reservation hoặc Static IP cố định | Static IP cố định do PO chỉ định (`192.168.1.x`) | **CHỜ IP CLIENT** |
| **Phân giải tên miền** | `88DB120531F23C4.local` (mDNS nội bộ) | Client B phải hỗ trợ mDNS hoặc cấu hình `hosts` | **SẴN SÀNG** |
| **SAN Chứng chỉ TLS** | Bao gồm cả `88DB120531F23C4.local` & `192.168.1.73` | Trình duyệt truy cập không báo lỗi Tên miền (SAN Match) | **SẴN SÀNG** |
| **Root CA Trust** | `%APPDATA%\caddy\pki\authorities\local\root.crt` | Cài đặt chứng chỉ Root CA vào Trust Store của Client B | **CHỜ PHÂN PHỐI** |
| **Giới hạn Tường lửa** | Rule: `AIVoiceStudio_LAN_Gateway_TCP_9443` | Cấu hình tham số `-RemoteAddress <Client_B_IP>` | **SẴN SÀNG** |
| **Cổng mạng khác** | Cổng Backend 8765 giữ `127.0.0.1` | Không cho phép kết nối trực tiếp vào 8765 | **ĐÃ KHÓA** |
| **Mở Internet / NAT** | Không có Port-Forwarding, UPnP tắt | Không có bất kỳ kết nối nào ra ngoài Internet | **BẢO MẬT** |
| **Địa chỉ MAC** | Đã ghi nhận địa chỉ MAC card mạng chủ | Thu thập làm metadata quản lý tài sản (không thay thế TLS) | **THÔNG TIN PHỤ** |

### Lệnh cài đặt và dọn dẹp Root CA trên Máy Khách B:
- **Cài đặt chứng chỉ trước thử nghiệm**:
  ```powershell
  Import-Certificate -FilePath .\root.crt -CertStoreLocation Cert:\CurrentUser\Root
  ```
- **Xóa chứng chỉ ngay sau khi hoàn thành Cổng A**:
  ```powershell
  Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Thumbprint -eq "C0294D0DC75A3EF3EEF911B842EE0072B0CF19B5829740695D22FF3018199A79" } | Remove-Item
  ```

---

## 5. QUY CHUẨN XÁC THỰC ROLLBACK TRONG PHIÊN GATE A (ROLLBACK READINESS)

Trong khuôn khổ phiên thử nghiệm Cổng A, kỹ sư triển khai phải thực hiện diễn tập rollback tại chỗ nhằm chứng minh:
1. **Kiểm tra tiến trình có chủ quyền**:
   - `scripts/lan_rollback.ps1` kiểm tra WMI: PID khớp, `ExecutablePath` chứa `caddy.exe`, dòng lệnh chứa `Caddyfile.lan`, thời điểm khởi tạo hợp lệ.
   - Nếu PID đã bị tái sử dụng cho ứng dụng khác, script từ chối tắt tiến trình và thông báo lỗi an toàn.
2. **Dọn dẹp chính xác quy tắc tường lửa**:
   - Xóa đúng quy tắc `AIVoiceStudio_LAN_Gateway_TCP_9443`.
   - Các quy tắc hệ thống khác không bị xáo trộn.
3. **Thời gian đáp ứng giải phóng cổng**:
   - Cổng 9443 trên card mạng LAN phải đóng hoàn toàn trong vòng **< 2 giây**.
4. **Khôi phục trạng thái Loopback**:
   - Kiểm tra tệp `infra/caddy/Caddyfile` sẵn sàng trên `127.0.0.1:9443`.
5. **Bảo toàn dữ liệu tuyệt đối**:
   - Xác thực `D:\AIVoiceStudioData\studio.db` và các tệp âm thanh có nguyên vẹn 100% kích thước và mã băm SHA-256.
