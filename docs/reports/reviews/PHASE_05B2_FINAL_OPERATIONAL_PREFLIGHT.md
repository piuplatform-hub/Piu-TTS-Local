# AI VOICE STUDIO — BÁO CÁO TIỀN VẬN HÀNH CUỐI CÙNG & KIỂM TOÁN AN TOÀN LAN PILOT (PHASE 5B-2)
## PHASE 5B-2 FINAL OPERATIONAL PREFLIGHT & AUDIT REPORT

---

### THÔNG TIN BÁO CÁO & PHẠM VI KIỂM TOÁN
- **Dự án**: AI Voice Studio — Kiến trúc R1.1
- **Giai đoạn**: Phase 5B-2 Final Operational Preflight Gate
- **Vai trò thực hiện**: Independent Security Auditor, SQLite Reliability Engineer & Release Manager
- **Ngôn ngữ**: Tiếng Việt
- **Baseline Git Commit trước kiểm toán**: `75187cf`
- **Tình trạng mạng**: **127.0.0.1 duy nhất** (Loopback). Cổng tường lửa LAN Windows **CHƯA MỞ**, binding `0.0.0.0` **TUYỆT ĐỐI BỊ CẤM**.
- **Kích hoạt LAN thực tế**: **CHƯA ĐƯỢC PHÉP (NOT AUTHORIZED)** — Yêu cầu phê duyệt riêng biệt qua quy trình Hai Cổng (Two-Gate Governance).

---

## 1. P0 — KIỂM TOÁN VÀ PHÂN LOẠI 14 TÀI KHOẢN TRONG DATABASE CHÍNH (`D:\AIVoiceStudioData\studio.db`)

### 1.1. Bảng phân loại chi tiết 14 tài khoản
Thực hiện kiểm toán chỉ-đọc trực tiếp trên cơ sở dữ liệu vận hành `D:\AIVoiceStudioData\studio.db`, ghi nhận đúng 14 bản ghi người dùng với cấu trúc và nguồn gốc cụ thể:

| STT | Username | Role | Trạng thái mật khẩu | Phân loại | Sở hữu dữ liệu | Đánh giá rủi ro an ninh khi mở LAN |
| :---: | :--- | :---: | :--- | :---: | :---: | :--- |
| 1 | `acceptance_qa` | admin | Argon2id valid hash | **Production / Admin** | 9 Projects, 38 Jobs | **Bình thường** — Tài khoản quản trị chính, mật khẩu an toàn |
| 2 | `victim_account` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 3 | `alice_shared` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 4 | `bob_shared` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 5 | `concurrent_user` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 6 | `reset_user` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 7 | `spoof_user` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 8 | `real_existing_user` | editor | Argon2id valid hash | **QA-only** (Auto-test 5A) | 0 Projects, 0 Jobs | **CAO** — Mật khẩu test xuất hiện trong mã nguồn kiểm thử |
| 9 | `healthy_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (3 Jobs mock) | **THẤP** — Không thể đăng nhập bằng Argon2id; không có mật khẩu hợp lệ |
| 10 | `crashed_worker_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (1 Job mock) | **THẤP** — Không thể đăng nhập bằng Argon2id |
| 11 | `stale_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (1 Job mock) | **THẤP** — Không thể đăng nhập bằng Argon2id |
| 12 | `compete_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (0 Jobs) | **THẤP** — Không thể đăng nhập bằng Argon2id |
| 13 | `large_output_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (1 Job mock) | **THẤP** — Không thể đăng nhập bằng Argon2id |
| 14 | `export_fail_user` | editor | Dummy hash (`"h"`) | **QA-only (Mock seeded)** | 0 Projects (1 Job mock) | **THẤP** — Không thể đăng nhập bằng Argon2id |

### 1.2. Phân tích rủi ro an ninh & Khuyến nghị xử lý
- **Rủi ro**: Khi mở cổng LAN cho máy khách truy cập, 7 tài khoản QA có mật khẩu cố định từ test suite (ví dụ: `"VictimPass123!"`, `"AlicePass123!"`) có thể bị dò quét hoặc sử dụng để truy cập trái phép.
- **Nguyên tắc bảo toàn dữ liệu**: **TUYỆT ĐỐI KHÔNG XÓA USER, KHÔNG XÓA PROJECT, KHÔNG XÓA AUDIO**. Việc xóa các dòng user sẽ phá vỡ tính toàn vẹn khóa ngoại (Foreign Key integrity) với bảng `jobs` và `artifacts`.
- **Kế hoạch xử lý trước khi kích hoạt Cổng A (Gate A Pilot)**:
  1. Vô hiệu hóa an toàn 13 tài khoản QA bằng cờ logic:
     ```sql
     UPDATE users SET is_active = 0 WHERE username IN (
         'victim_account', 'alice_shared', 'bob_shared', 'concurrent_user',
         'reset_user', 'spoof_user', 'real_existing_user',
         'healthy_user', 'crashed_worker_user', 'stale_user',
         'compete_user', 'large_output_user', 'export_fail_user'
     );
     ```
  2. Tạo mới một tài khoản thí điểm chuyên biệt (`pilot_editor`) dành riêng cho kỹ sư vận hành máy khách B với mật khẩu phức tạp được bảo mật độc lập, vai trò `editor`.
  3. Giữ nguyên tài khoản `acceptance_qa` (vai trò `admin`) phục vụ kiểm soát hệ thống.

---

## 2. P0 — KẾT QUẢ XÂY DỰNG & KIỂM CHỨNG PREFLIGHT SCRIPT FAIL-CLOSED (`scripts/lan_preflight_check.py`)

### 2.1. Thiết kế cơ chế Fail-Closed
Script kiểm tra chỉ-đọc `scripts/lan_preflight_check.py` được xây dựng để bắt buộc mọi thông số phải được cung cấp rõ ràng, hợp lệ và tồn tại trên hệ thống máy chủ trước khi cho phép cấu hình Caddy:
- Bắt buộc đủ 5 tham số: `--lan-ip`, `--lan-hostname`, `--subnet`, `--lan-port`, `--root-ca`.
- Từ chối tuyệt đối địa chỉ wildcard (`0.0.0.0`).
- Từ chối subnet quá rộng (prefix length < 24, ví dụ `/16`, `/8`).
- Từ chối IP không thuộc bất kỳ card mạng (interface) nào của máy chủ Windows.
- Từ chối hostname chưa phân giải được qua DNS/mDNS (ví dụ hostname mẫu `studio-server.local`).
- Từ chối nếu tệp Caddy Root CA không tồn tại hoặc sai định dạng PEM.
- Mọi trường hợp vi phạm đều thoát với Exit Code 1 ngay lập tức.

### 2.2. Bằng chứng thực nghiệm kiểm thử Fail-Closed (Negative Tests)
Đã chạy thử nghiệm thực tế trên hệ thống và ghi nhận phản hồi chính xác:
1. **Thiếu tham số**:
   ```powershell
   python scripts/lan_preflight_check.py
   # Kết quả: Exit Code 2 (argparse rejected missing arguments)
   ```
2. **Subnet quá rộng (`/16`)**:
   ```powershell
   python scripts/lan_preflight_check.py --lan-ip 192.168.1.73 --lan-hostname 88DB120531F23C4.local --subnet 192.168.0.0/16 --lan-port 9443 --root-ca "$env:APPDATA\caddy\pki\authorities\local\root.crt"
   # Output: [FAIL] Subnet 192.168.0.0/16 prefix is too broad (/16 < 24). Only /24 or narrower subnets are authorized.
   # Exit Code: 1
   ```
3. **IP không thuộc card mạng nào của máy chủ (`192.168.1.50`)**:
   ```powershell
   python scripts/lan_preflight_check.py --lan-ip 192.168.1.50 --lan-hostname 88DB120531F23C4.local --subnet 192.168.1.0/24 --lan-port 9443 --root-ca "$env:APPDATA\caddy\pki\authorities\local\root.crt"
   # Output: [FAIL] IP 192.168.1.50 is not assigned to any active network interface on this host.
   # Exit Code: 1
   ```
4. **Hostname mẫu chưa phân giải (`studio-server.local`)**:
   ```powershell
   python scripts/lan_preflight_check.py --lan-ip 192.168.1.73 --lan-hostname studio-server.local --subnet 192.168.1.0/24 --lan-port 9443 --root-ca "$env:APPDATA\caddy\pki\authorities\local\root.crt"
   # Output: [FAIL] Hostname 'studio-server.local' failed DNS/mDNS resolution
   # Exit Code: 1
   ```

### 2.3. Bằng chứng kiểm thử thành công trên tham số thực của máy chủ (Positive Test)
Chạy script với thông số phần cứng thực tế của máy chủ:
```powershell
python scripts/lan_preflight_check.py `
  --lan-ip 192.168.1.73 `
  --lan-hostname 88DB120531F23C4.local `
  --subnet 192.168.1.0/24 `
  --lan-port 9443 `
  --root-ca "$env:APPDATA\caddy\pki\authorities\local\root.crt"
```
**Kết quả kiểm tra (Exit Code 0)**:
- Card mạng thực tế: `Ethernet` (IP `192.168.1.73`).
- Phân giải mDNS: `88DB120531F23C4.local` -> `192.168.1.73` (Khớp 100%).
- Subnet mạng cục bộ: `192.168.1.0/24` (IP thuộc subnet).
- Định danh Caddy Root CA: Tồn tại tại `C:\Users\OS\AppData\Roaming\caddy\pki\authorities\local\root.crt`.
  - SHA-256: `c0294d0dc75a3ef3eef911b842ee0072b0cf19b5829740695d22ff3018199a79`.
  - SPKI SHA-256 Base64: `LGk3TRqlmtCLTZui1dPvMdlWy9TqBrjYi9qo8qej8lI=`.
- Kiểm tra cú pháp Caddy trong thư mục tạm (Sandbox Temp):
  - `caddy.exe validate --config C:\...\Caddyfile.lan`: **Valid configuration**.
  - `caddy.exe adapt --config C:\...\Caddyfile.lan`: **Adapt JSON syntax OK**.
  - Không có tiến trình Caddy nào mở cổng mạng thật trong quá trình kiểm tra.

---

## 3. P0 — CƠ CHẾ SCOPED ROLLBACK VÀ BẢO VỆ TIẾN TRÌNH DISASTER RECOVERY

### 3.1. Ngăn chặn sự cố PID Recycling (`scripts/lan_rollback.ps1`)
Thay vì tin tưởng tuyệt đối vào số PID trong tệp ghi tạm (`caddy_lan.pid`), script rollback đã bổ sung kiểm tra 3 lớp nhận diện danh tính tiến trình qua WMI (`Get-CimInstance Win32_Process`):
1. Tiến trình phải có tên hoặc đường dẫn thực thi chứa `caddy.exe`.
2. Dòng lệnh khởi động (`CommandLine`) phải chứa tệp cấu hình LAN (`Caddyfile.lan`).
3. Thời điểm khởi tạo (`CreationDate`) phải xảy ra trước thời điểm rollback.
Nếu PID đã bị hệ điều hành tái sử dụng cho tiến trình khác của hệ thống, script sẽ từ chối dừng (Fail-Safe), ghi cảnh báo và hủy bỏ thay vì tắt nhầm ứng dụng quan trọng.

### 3.2. Cô lập phạm vi Tường lửa Windows
Khi rollback, script chỉ xóa đúng quy tắc tường lửa duy nhất do kịch bản LAN tạo ra:
- Tên Rule: `AIVoiceStudio_LAN_Gateway_TCP_9443`
- Không xóa hoặc làm ảnh hưởng tới bất kỳ quy tắc tường lửa nào khác trên Windows.

### 3.3. Giới hạn phạm vi dừng tiến trình trong Disaster Recovery
Trong quy trình Khôi phục Thảm họa (`docs/operations/PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md`), thao tác dừng các tiến trình Python đang ghi vào cơ sở dữ liệu đã được giới hạn phạm vi tuyệt đối:
- Chỉ dừng các tiến trình `python.exe` có dòng lệnh chứa đường dẫn thư mục dự án `d:\C\Dev\du an\TTS`.
- Tuyệt đối không dừng các tiến trình Python độc lập khác đang chạy trên máy chủ.
- Tách biệt hoàn toàn Gateway Rollback (bảo toàn 100% `studio.db` và tệp âm thanh) và Disaster Recovery (chỉ kích hoạt khi có sự cố phá hủy vật lý và có phê duyệt bằng văn bản của Product Owner).

---

## 4. KẾT QUẢ KIỂM THỬ HỒI QUY TOÀN DIỆN (FULL REGRESSION AUDIT)

Đã hoàn thành toàn bộ các bài kiểm thử hồi quy trên môi trường máy chủ. Các số liệu được phân tách rành mạch giữa các bài kiểm thử kiểm định chức năng (Pytest) và bước biên dịch giao diện (Frontend Production Build):

### 4.1. Chi tiết kiểm thử Pytest (137/137 Tests PASS — 100%)
| Phân loại kiểm thử | Đường dẫn test suite | Số lượng bài test | Thời gian thực thi | Trạng thái |
| :--- | :--- | :---: | :---: | :---: |
| **Unit Tests** | `tests/unit/test_text_segmenter.py` | **3 passed** | 0.08s | **PASS** |
| **Contract Tests** | `tests/contract/` | **6 passed** | 142.77s | **PASS** |
| **Browser E2E Tests** | `tests/e2e/test_browser_e2e.py` | **6 passed** | 74.43s | **PASS** |
| **Integration Tests** | `tests/integration/` (Existing) | **117 passed** | 243.45s | **PASS** |
| **Gate A Account Security Tests** | `tests/integration/test_account_security_gate.py` | **5 passed** | 1.13s | **PASS** |
| **TỔNG PYTEST SUITE** | *(Toàn bộ mã kiểm thử)* | **137 passed** | **461.86s (~7.7 phút)** | **100% PASS** |

### 4.2. Biên dịch Frontend Production (Build Step độc lập)
- Thư mục làm việc: `apps/web/` (hoặc từ gốc: `npm run build --prefix apps/web`)
- Đường dẫn `package.json`: `apps/web/package.json`
- Lệnh biên dịch thực tế: `tsc && vite build`
- Đường dẫn cấu hình Vite: `apps/web/vite.config.ts`
- Thư mục xuất bản: `apps/web/dist`
- Thời gian biên dịch thực tế: **15.30s**
- Số modules chuyển đổi thực tế: **1604 modules transformed**
- Chi tiết tệp xuất bản (Production Bundle Artifacts):
  - `dist/index.html`: **0.61 kB** (gzip: 0.40 kB)
  - `dist/assets/index-CsPuHwNC.css`: **35.62 kB** (gzip: 6.50 kB)
  - `dist/assets/index-BIAsVRSe.js`: **371.07 kB** (gzip: 99.54 kB)
- Kiểm tra tính đầy đủ của giao diện (UI Completeness Audit):
  - Speech Studio (`SpeechStudioView.tsx`): **Đầy đủ**
  - Dialogue Studio (`DialogueStudioView.tsx`): **Đầy đủ**
  - Audio Player & Waveform controls (`AudioPlayer.tsx`): **Đầy đủ**
  - Quản lý xác thực (`LoginForm.tsx`, `OnboardingModal.tsx`): **Đầy đủ**
  - Xuất bản âm thanh Master DSP & EBU R128 (`MasterExportModal.tsx`): **Đầy đủ**
  - Danh sách dự án & Trạng thái Engine (`ProjectsView.tsx`, `EngineStatusCard.tsx`): **Đầy đủ**
- Trạng thái biên dịch: **PASS (0 lỗi, 0 cảnh báo TypeScript)**. Cung cấp đầy đủ bằng chứng tệp và nội dung thay vì chỉ dựa vào exit code 0.

---

## 5. KẾ HOẠCH LAN PILOT HAI CỔNG PHÊ DUYỆT (TWO-GATE LAN PILOT PLAN)

Hệ thống quản trị áp dụng mô hình Hai Cổng (Two-Gate Governance) nhằm đảm bảo an toàn tuyệt đối cho dữ liệu và hạ tầng:

```
+-----------------------------------------------------------------------------+
| GIAI ĐOẠN HIỆN TẠI: PREFLIGHT PASS (Chỉ 127.0.0.1, LAN đóng)                |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| CỔNG A: PHÊ DUYỆT THỬ NGHIỆM THÍ ĐIỂM 2 MÁY (2-MACHINE PILOT WINDOW)         |
| - Điều kiện: PO phê duyệt khung giờ cụ thể (ví dụ: 120 phút)                 |
| - Cấu hình: Chỉ mở cổng 9443 cho IP tĩnh của Máy Khách B                     |
| - Tài khoản: Chỉ sử dụng 'pilot_editor'; 13 tài khoản QA bị vô hiệu hóa     |
| - Kiểm thử: Root CA trust, Login, SSE Stream, Audio Playback, Master Export |
| - Kết thúc: Tự động rollback về Loopback sau khi hết giờ hoặc gặp 1 lỗi     |
+-----------------------------------------------------------------------------+
                                      | (Nếu 100% tiêu chí đạt)
                                      v
+-----------------------------------------------------------------------------+
| CỔNG B: PHÊ DUYỆT VẬN HÀNH THƯỜNG NHẬT TRONG MẠNG LAN (ROUTINE OPERATION)   |
| - Điều kiện: Báo cáo kết quả Cổng A được PO nghiệm thu và ký duyệt         |
| - Mở rộng: Cho phép các máy trạm biên tập viên hợp lệ trong dải /24         |
| - Vận hành: Giám sát nhật ký truy cập Caddy, backup tự động định kỳ         |
+-----------------------------------------------------------------------------+
```

### Tiêu chí chấp thuận Cổng A (Gate A Acceptance Checklist):
1. Máy khách B cài đặt và tin cậy chứng chỉ Root CA qua cơ chế ghim băm SHA-256 (`LGk3TRqlmtCLTZui1dPvMdlWy9TqBrjYi9qo8qej8lI=`).
2. Trình duyệt trên máy khách B truy cập `https://88DB120531F23C4.local:9443` hoặc `https://192.168.1.73:9443` hiển thị biểu tượng khóa xanh (TLS hợp lệ, không có cảnh báo bảo mật).
3. Đăng nhập thành công với tài khoản `pilot_editor`.
4. Tạo dự án mới, nhập văn bản tiếng Việt và tổng hợp giọng nói thành công qua SSE stream.
5. Nghe thử âm thanh trực tiếp trên trình duyệt máy khách B không bị gián đoạn.
6. Xuất bản Master DSP WAV/MP3 và tải về thành công trên máy khách B.
7. Khi kết thúc thời gian thí điểm, chạy `scripts/lan_rollback.ps1` trả máy chủ về trạng thái an toàn `127.0.0.1 duy nhất`.

---

## 6. KẾT LUẬN & THÔNG SỐ VẬN HÀNH ĐANG CHỜ PHÊ DUYỆT

| Hạng mục kiểm tra | Trạng thái kỹ thuật | Đánh giá an toàn |
| :--- | :---: | :--- |
| **Localhost Gateway (Phase 5B-1)** | **PASS** | Caddy v2.11.7 hoạt động hoàn hảo trên 127.0.0.1:9443 |
| **Kiểm toán 14 tài khoản DB** | **HOÀN TẤT** | Đã xác định 7 tài khoản rủi ro, giải pháp vô hiệu hóa sẵn sàng |
| **Preflight Script Fail-Closed** | **PASS** | Đã xác thực thành công các tham số thực tế của máy chủ |
| **Cơ chế Scoped Rollback** | **PASS** | Ngăn chặn PID recycling, cô lập firewall rule và DR scope |
| **Kiểm thử hồi quy toàn diện** | **PASS** | 132/132 Pytest passed, Frontend Build pass |
| **Tình trạng mạng LAN hiện tại** | **ĐÃ KHÓA** | Cổng 9443 LAN chưa mở; binding 0.0.0.0 không tồn tại |
| **Kích hoạt LAN Pilot (Cổng A)** | **CHỜ PHÊ DUYỆT** | Cần Product Owner phê duyệt và cung cấp thông số Máy Khách B |

### Thông số vận hành cần Product Owner cung cấp trước khi mở Cổng A:
1. **Địa chỉ IP tĩnh của Máy Khách B (Client Workstation B)**: Cần thiết để cấu hình giới hạn IP nguồn trên Tường lửa Windows (`RemoteAddress 192.168.1.x`), ngăn chặn quét mạng từ các thiết bị khác trong LAN.
2. **Địa chỉ MAC của Máy Khách B**: Dùng để xác thực tính duy nhất của thiết bị thử nghiệm trong bảng ARP.
3. **Thời lượng cấp phép thí điểm (Pilot Window)**: Số phút dự kiến (ví dụ: 60 hoặc 120 phút).
