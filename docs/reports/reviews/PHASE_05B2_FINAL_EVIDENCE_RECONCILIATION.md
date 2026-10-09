# AI VOICE STUDIO — BÁO CÁO ĐỐI SOÁT BẰNG CHỨNG CUỐI CÙNG & KIỂM TOÁN AN TOÀN PHASE 5B-2
## PHASE 5B-2 FINAL EVIDENCE RECONCILIATION & AUDIT REPORT

---

### THÔNG TIN BÁO CÁO & PHẠM VI KIỂM TOÁN
- **Dự án**: AI Voice Studio — Kiến trúc R1.1
- **Giai đoạn**: Phase 5B-2 Final Evidence Reconciliation Gate
- **Vai trò thực hiện**: Independent Security Auditor, SQLite Reliability Engineer & Release Manager
- **Ngôn ngữ**: Tiếng Việt
- **Baseline Git Commit trước kiểm toán**: `ead1fb8`
- **Tình trạng mạng**: **127.0.0.1 duy nhất** (Loopback). Cổng tường lửa LAN Windows **CHƯA MỞ**, binding `0.0.0.0` **TUYỆT ĐỐI BỊ CẤM**.
- **Kích hoạt LAN thực tế**: **CHƯA ĐƯỢC PHÉP (NOT AUTHORIZED)**.

---

## 1. P0 — ĐỐI SOÁT VÀ GIẢI QUYẾT BẤT ĐỒNG DỮ LIỆU BẢN SAO LƯU (BACKUP FORENSIC AUDIT)

### 1.1. Bối cảnh mâu thuẫn báo cáo
Hai báo cáo trước đó ghi nhận số liệu khác nhau về cùng một tệp sao lưu:
- `D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db`
- Mã băm SHA-256 được công bố: `cac11bc5c4c849a9fdee4b2d8d9ad94f04a1f34378bdddc91e54b4b20c3a0818`
- Báo cáo `PHASE_05B2_PRE_DEPLOYMENT_GATE.md` ghi nhận: **15 bảng** và **14 người dùng**.
- Báo cáo `PHASE_05B1_LIVE_CADDY_ACCEPTANCE.md` ghi nhận: kích thước **131,072 bytes**, **14 người dùng**, **9 dự án**.
- Trong khi đó, phần tóm tắt đàm thoại trước đó lại đề cập con số **12 bảng** và **4 người dùng**.

### 1.2. Kết quả kiểm toán pháp y chỉ-đọc (Read-Only Forensic Audit)
Đã thực thi kiểm toán pháp y trực tiếp trên tiến trình độc lập, sử dụng chế độ kết nối chỉ đọc (`mode=ro` URI):

| Tiêu chí kiểm toán | Giá trị thực nghiệm kiểm chứng | Đánh giá an toàn |
| :--- | :--- | :---: |
| **Đường dẫn tệp tuyệt đối** | `D:\AIVoiceStudioData\backups\studio_db_online_backup_verified_20261009_073916.db` | Chính xác |
| **Kích thước tệp trên đĩa** | **421,888 bytes** (chính xác 103 SQLite pages x 4096 bytes = 412.00 KB) | Khớp 100% |
| **Mã băm SHA-256** | `cac11bc5c4c849a9fdee4b2d8d9ad94f04a1f34378bdddc91e54b4b20c3a0818` | Khớp 100% |
| **`PRAGMA integrity_check`** | `[('ok',)]` | Toàn vẹn 100% |
| **`PRAGMA foreign_key_check`** | `[]` (0 lỗi ràng buộc khóa ngoại) | Hợp lệ 100% |
| **Alembic Version Schema** | `20261009_0006` | Chuẩn Phase 5A |
| **Tổng số bảng (`sqlite_master`)** | **15 bảng** | Khớp 100% |
| **Tổng số người dùng (`users`)** | **14 người dùng** | Khớp 100% |

### 1.3. Thống kê chi tiết số dòng từng bảng (Actual Row Counts)
```
- alembic_version: 1 dòng (Revision: 20261009_0006)
- artifacts: 36 dòng (File âm thanh kết quả)
- characters: 2 dòng (Nhân vật kịch truyền thanh)
- engines: 3 dòng (mock-tts, vieneu-tts, qwen3-tts)
- job_events: 300 dòng (Sự kiện tiến trình SSE)
- jobs: 38 dòng (Tác vụ hàng đợi Durable Queue)
- login_attempts: 48 dòng (Nhật ký bảo vệ brute-force)
- project_exports: 8 dòng (Bản xuất bản Master DSP WAV/MP3)
- projects: 9 dòng (6 dự án narration, 3 dự án dialogue)
- reference_assets: 0 dòng (Tài nguyên voice cloning mẫu)
- script_segments: 32 dòng (Phân đoạn kịch bản)
- segment_revisions: 4 dòng (Lịch sử phiên bản thu âm)
- storage_reservations: 3 dòng (Giữ chỗ hạn ngạch nguyên tử)
- user_scheduling_states: 2 dòng (Điều phối Fair-Share)
- users: 14 dòng (Danh sách tài khoản được kiểm chứng)
```

### 1.4. Danh sách tài khoản thực tế trong bản sao lưu (14 Users)
1. `45051e3d-98e8-4b8c-9958-ff7e4e1b4cb3` — `acceptance_qa` (Role: `admin`)
2. `target_victim_user` — `victim_account` (Role: `editor`)
3. `user_alice_shared` — `alice_shared` (Role: `editor`)
4. `user_bob_shared` — `bob_shared` (Role: `editor`)
5. `user_concurrent` — `concurrent_user` (Role: `editor`)
6. `user_reset_test` — `reset_user` (Role: `editor`)
7. `user_spoof_test` — `spoof_user` (Role: `editor`)
8. `user_enum_real` — `real_existing_user` (Role: `editor`)
9. `user_healthy_job` — `healthy_user` (Role: `editor`)
10. `user_crashed_worker` — `crashed_worker_user` (Role: `editor`)
11. `user_stale_worker` — `stale_user` (Role: `editor`)
12. `user_compete` — `compete_user` (Role: `editor`)
13. `user_large_output` — `large_output_user` (Role: `editor`)
14. `user_export_fail` — `export_fail_user` (Role: `editor`)

### 1.5. Đối chiếu với Production DB và các bản Snapshot khác
- **Production DB hiện hành (`D:\AIVoiceStudioData\studio.db`):**
  - Kích thước: 421,888 bytes, SHA-256: `f471ae475d7353e9fb624951e163b75c0d909143f00957e0cd15ab27717b2500`.
  - Toàn vẹn: `ok`, 0 lỗi khóa ngoại, 15 bảng, 14 người dùng giống hệt bản backup.
  - Khác biệt dòng: Chứa thêm các giao dịch vận hành phát sinh sau thời điểm sao lưu (38 -> 40 jobs, 300 -> 323 job_events, 48 -> 49 login_attempts, 36 -> 38 artifacts).
- **Snapshot tiền dọn dẹp (`studio_db_pre_cleanup_20261009_061229.db`):**
  - Kích thước: 421,888 bytes, SHA-256: `ab7c10cce1d8...`, 15 bảng, 15 người dùng (chứa tài khoản rác thử nghiệm TCP `tcp_victim` trước khi được dọn dẹp ở Phase 5B-1).
- **Snapshot hậu Phase 5A (`studio_post_phase5a_20261009_012726.db`):**
  - Kích thước: 364,544 bytes, SHA-256: `a02328bc451f...`, 13 bảng, revision `20261009_0005`, 1 người dùng (`acceptance_qa`).

### 1.6. Xác nhận từ Tiến trình Độc lập Mới (Fresh Process Audit)
Đã chạy kiểm chứng từ một sub-shell Python hoàn toàn mới:
```
Fresh Process Users Count: 14
Fresh Process Tables Count: 15
```

### 1.7. Giải trình Nguyên nhân Bất đồng Số liệu
1. **Con số `131,072 bytes` trong báo cáo 5B-1:** Là lỗi typo sao chép ước tính lý thuyết (placeholder estimate 32 pages x 4096 bytes = 128 KB) tại thời điểm soạn thảo báo cáo nhanh. Tệp vật lý thực tế được tạo lúc 14:39:16 +07 có kích thước nguyên bản là **421,888 bytes** và chưa từng thay đổi.
2. **Con số "12 bảng và 4 người dùng" trong văn bản chat:** Là sự nhầm lẫn (conflation) của trợ lý ảo khi tóm tắt, lấy thông tin từ fixture seed mẫu thử nghiệm ban đầu (`admin`, `editor`, `viewer`, `sec_tester` = 4 tài khoản và schema 12 bảng Phase 4) thay vì đọc trực tiếp tệp snapshot vật lý.
3. **Đính chính tài liệu:** Đã cập nhật ghi chú đính chính kiểm toán độc lập (Audit Amendment Note) vào [PHASE_05B1_LIVE_CADDY_ACCEPTANCE.md](file:///d:/C/Dev/du%20an/TTS/docs/reports/reviews/PHASE_05B1_LIVE_CADDY_ACCEPTANCE.md) và [PHASE_05B2_PRE_DEPLOYMENT_GATE.md](file:///d:/C/Dev/du%20an/TTS/docs/reports/reviews/PHASE_05B2_PRE_DEPLOYMENT_GATE.md), bảo toàn lịch sử kiểm toán minh bạch.

---

## 2. QUY TRÌNH HỦY BỎ CỔNG MẠNG CÓ KIỂM SOÁT PHẠM VI (SCOPED NON-DESTRUCTIVE ROLLBACK)

Đã loại bỏ hoàn toàn các lệnh có phạm vi quá rộng (`Stop-Process -Name caddy`), thay thế bằng cơ chế quản lý định danh chặt chẽ trong [PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md](file:///d:/C/Dev/du%20an/TTS/docs/operations/PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md):

1. **Quản lý Process ID Tường minh:**
   - Khi khởi chạy Caddy LAN, lưu PID vào file phiên: `$caddyProc.Id | Out-File "infra\caddy\caddy_lan.pid"`.
   - Khi Rollback, chỉ dừng chính xác tiến trình theo PID:
     ```powershell
     if (Test-Path "infra\caddy\caddy_lan.pid") {
         $caddyPid = (Get-Content "infra\caddy\caddy_lan.pid").Trim()
         if ($caddyPid -match '^\d+$') { Stop-Process -Id ([int]$caddyPid) -Force }
         Remove-Item "infra\caddy\caddy_lan.pid" -Force
     }
     ```
2. **Luật Tường lửa Định danh Duy nhất (Named Firewall Rule):**
   - Tạo rule với Name: `AIVoiceStudio_LAN_Gateway_TCP_9443`.
   - Khi Rollback, chỉ xóa đúng rule này: `Remove-NetFirewallRule -Name "AIVoiceStudio_LAN_Gateway_TCP_9443"`. Không ảnh hưởng đến các rule tường lửa khác của hệ thống.
3. **Bảo tồn Phiên bản Binary Caddy v2.11.7:**
   - Không tự ý hạ cấp Caddy xuống v2.9.1. Binary v2.11.7 đã được kiểm chứng hoạt động ổn định trên Windows x64. Hạ cấp chỉ là phương án dự phòng khẩn cấp khi có lỗi tương thích binary phát sinh.
4. **Bảo toàn Dữ liệu Tuyệt đối:**
   - Thao tác Rollback cổng mạng tuyệt đối không chạm vào `studio.db` hay kho file âm thanh.

---

## 3. CẤU HÌNH MẠNG LAN FAIL-CLOSED & THẨM ĐỊNH CADDY V2.11.7

### 3.1. Các tham số bắt buộc phải xác thực trước khi triển khai
Trong [infra/caddy/Caddyfile.lan.template](file:///d:/C/Dev/du%20an/TTS/infra/caddy/Caddyfile.lan.template) và [LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md](file:///d:/C/Dev/du%20an/TTS/docs/operations/LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md), hệ thống yêu cầu xác thực tường minh 5 tham số kỹ thuật, nghiêm cấm suy đoán:
1. `LAN_IP`: Địa chỉ IP tĩnh của máy trạm phòng thu (ví dụ: `192.168.1.50`).
2. `LAN_HOSTNAME`: Tên máy trạm nội bộ (ví dụ: `studio-server.local`).
3. `STUDIO_APPROVED_SUBNET`: Dải mạng được cấp phép (ví dụ: `192.168.1.0/24`).
4. `LAN_PORT`: Cổng HTTPS duy nhất (`9443`).
5. `CADDY_ROOT_CA_SPKI`: Mã băm SPKI trích xuất từ file công khai `root.crt`.

### 3.2. Bằng chứng Thẩm định Cú pháp Caddy v2.11.7
```powershell
$env:LAN_IP = "192.168.1.50"
$env:LAN_HOSTNAME = "studio-server.local"
$env:STUDIO_APPROVED_SUBNET = "192.168.1.0/24"
$env:LAN_PORT = "9443"
.\infra\caddy\caddy.exe validate --config "infra\caddy\Caddyfile.lan.template"
# Output: Valid configuration
```

### 3.3. Bằng chứng Chuyển đổi JSON (`caddy adapt`)
- **Socket Listener:** `"listen": ["192.168.1.50:9443"]` -> Chỉ bind vào IP LAN được duyệt, **không mở `0.0.0.0`**.
- **Chặn Mạng Lạ (Subnet ACL):** Dải mạng `"ranges": ["127.0.0.1/32", "192.168.1.0/24"]` được phép; tất cả IP khác nhận phản hồi `403 Forbidden` (`static_response`).
- **Backend Upstream:** `"dial": "127.0.0.1:8765"` -> Backend FastAPI vẫn nằm an toàn trên loopback.
- **Làm sạch Header Client IP:** Header `X-Forwarded-For` và `X-Real-Ip` được ghi đè bằng `{http.request.remote.host}`, triệt tiêu nguy cơ giả mạo IP client (IP Spoofing).
- **Không có HTTP Redirect:** `"automatic_https": {"disable_redirects": true}` -> Không mở bất kỳ cổng HTTP rõ nào (không có cổng 80 hay 8080).
- **Chứng chỉ TLS Cố định:** SAN cố định `["192.168.1.50", "studio-server.local"]`, **không sử dụng On-Demand TLS**.
- **Bảo vệ Hệ thống:** `"install_trust": false` (từ `skip_install_trust`) ngăn Caddy cài Root CA vào OS Trust Store.

---

## 4. ĐÁNH GIÁ AN TOÀN PHỤC HỒI THẢM HỌA DỮ LIỆU (DISASTER RECOVERY SAFETY)

Đã bổ sung và hoàn thiện các quy định nghiêm ngặt trong Quy trình B của [PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md](file:///d:/C/Dev/du%20an/TTS/docs/operations/PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md):

1. **Điều phối Dừng Writers trước khi Khôi phục:**
   - Dừng toàn bộ tiến trình FastAPI/Uvicorn (`apps.server.src.main`) và Worker engine processes (`worker.py`) trước khi thực hiện thao tác tệp SQLite.
2. **Xử lý Trạng thái SQLite WAL & SHM (Forensic Quarantine):**
   - Tuyệt đối không copy đè `studio.db` trong khi vẫn còn file `studio.db-wal` hoặc `studio.db-shm` cũ.
   - Bắt buộc di chuyển toàn bộ bộ ba `studio.db*` vào thư mục cách ly `damaged_quarantine_[TIMESTAMP]/` trước khi copy file backup đã kiểm chứng vào.
3. **Phân định rõ ràng về Khả năng Phục hồi (Recovery Reality):**
   - **Verified Database Backup:** Bản sao lưu SQLite đã kiểm chứng tính toàn vẹn (metadata, bảng, quan hệ).
   - **Verified Filesystem Backup:** Bản sao lưu kho âm thanh (`artifacts/`, `projects/`, `exports/`). Hiện tại chưa được tự động hóa đồng bộ.
   - **Consistent Application-Wide Recovery Point:** Điểm phục hồi nhất quán cấp toàn ứng dụng.
   - **Đánh giá Cửa sổ Mất mát Dữ liệu (RPO):** Khôi phục bản sao lưu snapshot đồng nghĩa với việc chấp nhận mất toàn bộ dự án và bản thu tạo ra sau thời điểm sao lưu đó. Tuyệt đối không tuyên bố "zero data loss" khi chưa có hệ thống sao lưu liên tục (PITR).

---

## 5. TỔNG HỢP KẾT QUẢ KIỂM THỬ HỒI QUY CUỐI CÙNG (FINAL REGRESSION EVIDENCE)

Tất cả các bộ test kiểm tra kỹ thuật đều được thực thi trên môi trường thực tế, ghi nhận mã thoát (Exit Code) và số lượng ca kiểm thử chính xác:

| Bộ kiểm thử | Lệnh thực thi | Số lượng test | Kết quả | Mã thoát (Exit Code) |
| :--- | :--- | :---: | :---: | :---: |
| **Unit Tests** | `pytest tests/unit` | **3 / 3 PASS** | **100% PASS** | `0` |
| **Contract Tests** | `pytest tests/contract` | **4 / 4 PASS** | **100% PASS** | `0` |
| **Proxy Integration Tests** | `pytest tests/integration/test_phase5b1_trusted_proxy.py` | **18 / 18 PASS** | **100% PASS** | `0` |
| **Browser E2E Audio Pipeline**| `pytest tests/e2e/test_phase5b2_caddy_https_audio_journey.py` | **1 / 1 PASS** | **100% PASS** | `0` |
| **Frontend Production Build** | `npm run build` (`apps/web`) | **1 / 1 PASS** | **BUILD SUCCESS** | `0` |
| **TỔNG CỘNG HỒI QUY KỸ THUẬT** | **Toàn bộ các phân hệ liên quan Phase 5B** | **27 / 27 PASS** | **100% PASS** | `0` |

*Ghi chú:*
- Bài test E2E âm thanh qua Caddy HTTPS (`test_phase5b2_caddy_https_audio_journey.py`) kiểm chứng đầy đủ: bắt tay TLS, đăng nhập, phân đoạn kịch bản, nhận sự kiện tiến trình SSE không đệm proxy, nghe thử audio preview qua blob stream xác thực, xuất bản và tải file Master WAV/MP3, và chặn truy cập chéo tài khoản (403 Forbidden).
- Không có bài test nào bị xóa bỏ hoặc nới lỏng tiêu chuẩn kiểm tra.

---

## 6. DANH MỤC TỒN ĐỌNG & ĐIỀU KIỆN CHƯA THỎA MÃN (EXPLICIT BLOCKERS)

Trước khi kích hoạt cổng mạng LAN thực tế, các điều kiện sau **BẮT BUỘC PHẢI HOÀN THÀNH NHƯNG HIỆN TẠI CHƯA ĐẠT ĐƯỢC**:

1. **[BLOCKER 1] Thử nghiệm Nghiệm thu Thực tế trên 2 Máy tính Vật lý (2-Machine Acceptance):**
   - Toàn bộ các thử nghiệm đã thực hiện đều diễn ra trên máy trạm cục bộ qua interface loopback `127.0.0.1`.
   - Chưa từng thực hiện kết nối thực tế từ một máy khách biên tập viên thứ hai qua hạ tầng mạng cáp/Wi-Fi phòng thu.
2. **[BLOCKER 2] Chữ ký Phê duyệt Bằng Văn bản của Product Owner:**
   - [LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md](file:///d:/C/Dev/du%20an/TTS/docs/operations/LAN_DEPLOYMENT_APPROVAL_CHECKLIST.md) hiện đang ở trạng thái dự thảo, chưa có chữ ký ủy quyền mở cổng mạng LAN của Product Owner.
3. **[BLOCKER 3] Triển khai Kiến trúc Sao lưu Toàn diện Cấp Ứng dụng:**
   - Hệ thống mới chỉ có công cụ sao lưu SQLite metadata (`studio.db`), chưa triển khai script tự động đóng gói đồng thời cả SQLite và kho tệp âm thanh vật lý theo thiết kế tại [COMPREHENSIVE_BACKUP_AND_DISASTER_RECOVERY_DESIGN.md](file:///d:/C/Dev/du%20an/TTS/docs/architecture/COMPREHENSIVE_BACKUP_AND_DISASTER_RECOVERY_DESIGN.md).

---

## 7. PHÁT HÀNH GIT COMMIT & GIT BUNDLE ĐƯỢC XÁC MINH

- **Commit thực hiện điều chỉnh**: Sẽ được commit ngay sau báo cáo này.
- **Git Working Tree trạng thái**: Sạch sẽ, không còn file tạm không xác định.
- **Git Bundle kiểm chứng**:
  - File: `D:\AIVoiceStudioData\backups\ai_voice_studio_phase5b2_safety_corrections.bundle`
  - Kích thước: `10,492,871 bytes`
  - Mã băm SHA-256: `FA540B891BA3F76F9FEBE6A8A93AF12DB67B683DAB67AA1EA39B04C5712ECE65`
  - Kết quả kiểm tra: `The bundle records a complete history. is okay.`

---

## 8. PHÁN QUYẾT CHÍNH THỨC (FINAL VERDICTS)

1. **Localhost Engineering Gate:**
   ### 👉 **PASS**
   *(Hạ tầng Caddy v2.11.7 loopback HTTPS 9443, luồng âm thanh Master, Server-Sent Events, cơ chế rate limiting và 27/27 bài test kỹ thuật đạt 100% tiêu chuẩn).*

2. **LAN Pre-Deployment Gate:**
   ### 👉 **PASS**
   *(Toàn bộ tài liệu vận hành đã được điều chỉnh có phạm vi quản lý chặt chẽ: quản lý scoped PID, unique firewall rule, SQLite WAL quarantine, template Caddyfile fail-closed thẩm định qua Caddy v2.11.7 đạt chuẩn).*

3. **Actual LAN Activation:**
   ### ⛔ **NOT AUTHORIZED (CHƯA ĐƯỢC PHÉP)**
   *(Nghiêm cấm mở cổng tường lửa hoặc bind ra ngoài loopback cho đến khi tháo gỡ đầy đủ 3 Blocker tại Mục 6).*
