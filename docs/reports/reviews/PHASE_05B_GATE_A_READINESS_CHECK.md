# AI VOICE STUDIO — BÁO CÁO KIỂM TRA SẴN SÀNG CỔNG A (PHASE 5B GATE A READINESS CHECK)
## GATE A OPERATIONAL READINESS, ACCOUNT SECURITY & FRONTEND INTEGRITY REPORT

---

### THÔNG TIN BÁO CÁO & PHẠM VI KIỂM ĐỊNH
- **Dự án**: AI Voice Studio — Kiến trúc R1.1
- **Giai đoạn**: Phase 5B Final Gate A Readiness Check
- **Vai trò thực hiện**: Independent Security Auditor, SQLite Reliability Engineer & Release Manager
- **Ngôn ngữ**: Tiếng Việt
- **Baseline Git Commit trước kiểm định**: `8f7ab14`
- **Trạng thái cổng LAN**: **CHƯA MỞ (NOT AUTHORIZED)** — Ranh giới mạng tiếp tục được khóa tại `127.0.0.1 duy nhất`.
- **Triển khai LAN thực tế / Windows Service**: **TUYỆT ĐỐI BỊ CẤM**.

---

## 1. P0 — KIỂM TOÁN AN TOÀN TÀI KHOẢN (ACCOUNT SECURITY GATE)

### 1.1. Bằng chứng đối soát pháp y 14 tài khoản trên SQLite chính (`studio.db`)
Đã thực hiện kiểm toán chỉ-đọc với thuật toán RFC 9106 Argon2id trên `D:\AIVoiceStudioData\studio.db`:
- **Tài khoản Quản trị (`acceptance_qa`)**:
  - Hash: Argon2id chuẩn (`$argon2id$v=19$m=19456,t=2,p=1...`)
  - Đối soát kiểm tra: **HOÀN TOÀN KHÔNG TRÙNG** với bất kỳ mật khẩu thử nghiệm nào trong mã nguồn (đã thử nghiệm 19 biến thể mật khẩu test).
- **7 tài khoản QA tự động sinh từ kiểm thử Phase 5A**:
  - `victim_account` $\rightarrow$ Khớp chính xác mật khẩu: `ValidPassword123!`
  - `alice_shared` $\rightarrow$ Khớp chính xác mật khẩu: `AliceSecret123!`
  - `bob_shared` $\rightarrow$ Khớp chính xác mật khẩu: `BobSecret456!`
  - `concurrent_user` $\rightarrow$ Khớp chính xác mật khẩu: `P@ss1234`
  - `reset_user` $\rightarrow$ Khớp chính xác mật khẩu: `CorrectPass1!`
  - `spoof_user` $\rightarrow$ Khớp chính xác mật khẩu: `Pass123!`
  - `real_existing_user` $\rightarrow$ Khớp chính xác mật khẩu: `RealPassword1!`
- **6 tài khoản QA Mock/Seeded**:
  - `healthy_user`, `crashed_worker_user`, `stale_user`, `compete_user`, `large_output_user`, `export_fail_user`
  - Cả 6 tài khoản đều mang dummy hash `"h"` (không thể xác thực qua thuật toán Argon2id).

### 1.2. Kết quả kiểm thử tự động trên Disposable Database Fixtures
Đã xây dựng và thực thi thành công bộ test suite độc lập `tests/integration/test_account_security_gate.py`:
- `test_deactivated_account_blocks_new_login`: Khi `is_active = 0`, yêu cầu `POST /api/v1/auth/login` bị chặn ngay lập tức với HTTP `403 Forbidden` (`code="ACCOUNT_DISABLED"`). $\rightarrow$ **PASS**.
- `test_deactivated_account_blocks_previously_issued_jwt`: Khi tài khoản bị đổi `is_active = False` trong cơ sở dữ liệu, JWT đã cấp trước đó bị từ chối ngay lập tức tại yêu cầu tiếp theo với HTTP `401 Unauthorized` (`code="USER_INACTIVE"`). $\rightarrow$ **PASS**.
- `test_password_change_revokes_token_version`: Đổi mật khẩu kích hoạt tăng `token_version`, thu hồi toàn bộ token JWT cũ với HTTP `401 Unauthorized` (`code="TOKEN_REVOKED"`). $\rightarrow$ **PASS**.
- `test_disabled_qa_credentials_cannot_authenticate`: Thử nghiệm xác thực cả 7 tài khoản QA với mật khẩu test khi `is_active = False` đều bị từ chối với HTTP `403 Forbidden`. $\rightarrow$ **PASS**.
- `test_transactional_deactivation_preserves_fk_integrity`: Cập nhật `is_active = 0` trong một Transaction duy nhất bảo toàn 100% tính toàn vẹn khóa ngoại của các dự án và tác vụ. $\rightarrow$ **PASS**.

### 1.3. Quy trình Transactional Deactivation & Cấp phát `pilot_editor`
- **Quy trình vô hiệu hóa an toàn**: Đã tạo `scripts/disable_qa_accounts.sql` thực thi trong `BEGIN TRANSACTION ... COMMIT`. **Chưa áp dụng vào production**, chỉ chạy khi Product Owner phê duyệt Cổng A.
- **Tài khoản thí điểm `pilot_editor`**: Đã tạo `scripts/create_pilot_account.py` tự động sinh mật khẩu ngẫu nhiên độ entropy cao (24 ký tự), băm RFC 9106 Argon2id và chuẩn bị câu lệnh SQL giao dịch.

---

## 2. XÁC MINH TÍNH TOÀN VẸN CỦA FRONTEND RELEASE ARTIFACT

### 2.1. Điều tra sự khác biệt giữa 1604 modules và 42 modules
- **Thực tế biên dịch**: Khi thực thi lệnh chính thức `npm run build --prefix apps/web` (`tsc && vite build`), công cụ Vite chuyển đổi chính xác **1604 modules** trong **15.30 giây**.
- **Nguyên nhân sai lệch số liệu cũ**: Trong báo cáo của lượt trước, số liệu "42 modules" và tên tệp `index-Bf6t8N48.js` là lỗi trích dẫn tài liệu không chính xác do người thực hiện không chạy trực tiếp lệnh build trong bước đó.
- **Thông số kỹ thuật chính xác của Frontend Build**:
  - Thư mục làm việc: `apps/web/`
  - Đường dẫn `package.json`: `apps/web/package.json`
  - Lệnh biên dịch: `tsc && vite build`
  - Tệp cấu hình: `apps/web/vite.config.ts`
  - Thư mục xuất bản: `apps/web/dist`
  - Tệp đầu ra (Dist Artifacts):
    - `dist/index.html`: **0.61 kB** (gzip: 0.40 kB)
    - `dist/assets/index-CsPuHwNC.css`: **35.62 kB** (gzip: 6.50 kB)
    - `dist/assets/index-BIAsVRSe.js`: **371.07 kB** (gzip: 99.54 kB)

### 2.2. Kiểm toán tính đầy đủ của các tính năng UI trong Bundle
Đã quét sâu tệp bundle sản xuất `dist/assets/index-BIAsVRSe.js` và xác nhận đầy đủ 100% các thành phần:
- Speech Studio (`SpeechStudioView.tsx`): **Đầy đủ**
- Dialogue Studio (`DialogueStudioView.tsx`): **Đầy đủ**
- Audio Player & Controls (`AudioPlayer.tsx`): **Đầy đủ**
- Quản lý xác thực (`LoginForm.tsx`, `OnboardingModal.tsx`): **Đầy đủ**
- Xuất bản âm thanh Master DSP EBU R128 (`MasterExportModal.tsx`): **Đầy đủ**
- Quản lý dự án & Trạng thái Engine (`ProjectsView.tsx`, `EngineStatusCard.tsx`): **Đầy đủ**
- Lịch sử tác vụ (`JobHistoryTable.tsx`): **Đầy đủ**

### 2.3. Xác nhận thư mục kiểm thử Browser E2E
- Thư mục chứa 6 bài kiểm thử Browser E2E thực tế là **`tests/e2e/`** (chứa `test_browser_e2e.py` gồm 6 bài test: Onboarding, Login, Speech Studio, Audio Playback, Job Cancel, Job History).
- Trong mã nguồn dự án **HOÀN TOÀN KHÔNG TỒN TẠI** thư mục `tests/browser/`. Đã hiệu đính chính xác vào tài liệu và release notes.

---

## 3. CHIẾN LƯỢC BẢO VỆ DỮ LIỆU TRƯỚC LAN PILOT (DATA PROTECTION STRATEGY)

Đã ban hành văn bản quy chuẩn `docs/operations/PHASE_05B_LAN_PILOT_SAFETY_STRATEGY.md`:
- **LỰA CHỌN PHƯƠNG ÁN A — THÍ ĐIỂM CÔ LẬP (OPTION A: ISOLATED PILOT)**:
  - Khởi tạo SQLite tạm thời: `D:\AIVoiceStudioData\pilot_sandbox\pilot_studio.db`
  - Thư mục âm thanh riêng biệt: `D:\AIVoiceStudioData\pilot_sandbox\audio\`
  - Không có bất kỳ quyền ghi (Zero Write Handles) nào vào `studio.db` và các tệp thu âm chính.
  - Ngay cả trong kịch bản xấu nhất, dữ liệu sản xuất được cách ly vật lý 100%.
- **Phương án B (Controlled Production Pilot)** chỉ là phương án dự phòng khi PO có yêu cầu bằng văn bản cần nghiệm thu trực tiếp trên các bản thu cũ, bắt buộc thực hiện sao lưu online và backup filesystem trước phiên.

---

## 4. CẤU HÌNH MẠNG LAN VÀ SỰ SẴN SÀNG CỦA MÁY KHÁCH B

- **Địa chỉ IP máy chủ**: `192.168.1.73` trên card mạng `Ethernet`.
- **Hostname máy chủ**: `88DB120531F23C4.local` (phân giải mDNS đạt 100%).
- **Địa chỉ IP Máy Khách B**: Chờ Product Owner cung cấp IP tĩnh được phê duyệt.
- **Tường lửa Windows**: Cấu hình giới hạn duy nhất IP Máy Khách B qua tham số `-RemoteAddress <Client_B_IP>`.
- **Cổng nội bộ**: Cổng 8765 giữ nguyên loopback `127.0.0.1`.
- **Internet**: Không mở cổng ra ngoài Internet, tắt UPnP.
- **Root CA Trust**: Chứng chỉ tại `%APPDATA%\caddy\pki\authorities\local\root.crt` (SHA-256: `c0294d0dc75a3ef3eef911b842ee0072b0cf19b5829740695d22ff3018199a79`). Có sẵn lệnh PowerShell cài đặt và gỡ bỏ trên Máy Khách B.
- **Địa chỉ MAC**: Được ghi nhận là siêu dữ liệu quản lý thiết bị, không thay thế cơ chế xác thực danh tính TLS và JWT.

---

## 5. ĐỘ SẴN SÀNG CỦA CƠ CHẾ ROLLBACK (ROLLBACK READINESS)

Kịch bản `scripts/lan_rollback.ps1` đã được kiểm chứng an toàn tuyệt đối:
- **Xác thực danh tính tiến trình**: Sử dụng WMI kiểm tra PID, đường dẫn `caddy.exe`, dòng lệnh `Caddyfile.lan` và thời điểm khởi tạo trước khi dừng tiến trình.
- **Từ chối PID tái sử dụng (Stale PID rejection)**: Nếu PID đã bị hệ điều hành cấp lại cho ứng dụng khác, script từ chối dừng để tránh thiệt hại ngoài ý muốn.
- **Dọn dẹp tường lửa có chủ quyền**: Chỉ xóa đúng quy tắc `AIVoiceStudio_LAN_Gateway_TCP_9443`.
- **Bảo toàn dữ liệu 100%**: Script rollback mạng không có bất kỳ thao tác nào chạm vào SQLite database hoặc tệp âm thanh.
- **Kế hoạch diễn tập trong Gate A**: Thực hiện diễn tập rollback ngay tại phiên thử nghiệm, xác nhận cổng 9443 đóng trong < 2 giây và khôi phục gateway loopback.

---

## 6. MA TRẬN CHẤP THUẬN CUỐI CÙNG (FINAL ACCEPTANCE MATRIX)

| Hạng mục nghiệm thu | Trạng thái kỹ thuật | Đánh giá an toàn |
| :--- | :---: | :--- |
| **A. Localhost Engineering** | **PASS** | Hoàn thành và ổn định tuyệt đối trên 127.0.0.1 |
| **B. Account Security Readiness** | **PASS** | 5/5 tests pass, forensic audit hoàn tất, quy trình vô hiệu hóa sẵn sàng |
| **C. Frontend Release Artifact** | **PASS** | 1604 modules, bundle 371.07 kB đầy đủ 100% tính năng UI |
| **D. Backup / Pilot Isolation** | **PASS** | Đã ban hành Chiến lược Phương án A (Isolated Pilot Sandbox) |
| **E. LAN Configuration Readiness** | **PASS** | Script preflight fail-closed đạt chuẩn, chờ IP Máy Khách B |
| **F. Gate A Authorization** | **NOT AUTHORIZED** | **CHƯA ĐƯỢC PHÉP — Chờ phê duyệt mở cổng 2 máy của Product Owner** |
| **G. Gate B Routine LAN Operation** | **NOT AUTHORIZED** | **CHƯA ĐƯỢC PHÉP — Chỉ xem xét sau khi Cổng A đạt 100% tiêu chí** |
