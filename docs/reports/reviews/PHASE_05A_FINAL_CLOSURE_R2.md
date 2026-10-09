# AI Voice Studio — Báo Cáo Thẩm Định Đóng Giai Đoạn 5A Final Closure R2
## ĐIỀU TIẾT XÁC THỰC ĐA TẦNG, AN TOÀN HẠN NGẠCH THUÊ VÀ XỬ LÝ LŨY TIẾN TỰ TRỊ

**Vai trò:** Principal Backend Security Engineer, Distributed Systems Engineer, Release QA Lead  
**Trạng thái thẩm định:** CHẤP THUẬN HOÀN TOÀN (ACCEPTANCE PASS)  
**Ngày thẩm định:** 09/10/2026  
**Commit cơ sở:** `6161612` (R1) $\to$ Final Closure R2  
**Môi trường:** Máy trạm cục bộ (Local Workstation `127.0.0.1`), Windows 11, SQLite WAL Mode  
**Phạm vi:** Đóng dứt điểm Phase 5A. **Nghiêm cấm triển khai Phase 5B, không mở mạng LAN, không cài Caddy, không cấu hình Windows Services.**

---

## 1. TỔNG QUAN VÀ ĐÁNH GIÁ CHUNG (EXECUTIVE SUMMARY)

Đợt thẩm định độc lập **Phase 5A Final Closure R2** đã hoàn tất việc rà soát, vá lỗi bảo mật chuyên sâu và kiểm chứng độ tin cậy của toàn bộ hệ thống đa người dùng cục bộ cho AI Voice Studio.

Các kết quả then chốt đạt được trong phiên bản R2:
1. **Hệ thống điều tiết xác thực 3 tầng (Priority P0)**: Triển khai cơ chế phòng thủ độc lập chống brute-force phân tán (theo tài khoản $\ge 10$), credential spraying (theo IP nguồn $\ge 20$), và mật khẩu sai lặp lại (theo cặp IP-User $\ge 5$). Xác định địa chỉ IP máy khách tuyệt đối dựa trên socket peer (`request.client.host`), hoàn toàn vô hiệu hóa kỹ thuật giả mạo header `X-Forwarded-For`.
2. **Vòng đời đặt trước hạn ngạch nguyên tử (Atomic Quota Reservation Lifecycle)**: Gia hạn TTL reservation thông qua worker heartbeat định kỳ, bảo vệ an toàn các tác vụ đang chạy/chờ xử lý khỏi việc thu hồi sớm, từ chối công nhân trễ hạn (stale worker) với mã lỗi `HTTP 409 Conflict`, đối soát dung lượng thực tế và xóa bỏ tệp rác tạm thời khi export thất bại.
3. **Phân tích thực nghiệm độ ưu tiên và hiện tượng bỏ đói (Priority Scheduling & Starvation Trade-offs)**: Chứng minh tính công bằng tuyệt đối giữa các người dùng cùng độ ưu tiên, xác nhận cơ chế Head-of-Line Priority Precedence giữa các cấp độ ưu tiên khác nhau, và tài liệu hóa đầy đủ lý do kỹ thuật tại sao hệ thống không áp dụng cơ chế Priority Aging nhằm bảo vệ mục tiêu kinh doanh/vận hành phòng thu.
4. **Xử lý batch dài tập tự trị (Autonomous Progressive Batch Processing)**: Chứng minh thành công kịch bản nộp 100 phân đoạn kịch bản mà **không cần bất kỳ lệnh poll nào từ trình duyệt (`GET /projects`)**. Hệ thống nền (daemon runner) tự động điều tiết nạp từng nhóm 25 tác vụ, vượt qua an toàn các sự cố khởi động lại tiến trình API và tiến trình Runner, bảo đảm 100/100 phân đoạn hoàn tất và 100 audio artifact độc bản duy nhất.
5. **Sao lưu trực tuyến SQLite qua CLI chính thức**: Hoàn thành kiểm chứng lệnh `python -m apps.server.src.backup create` và `verify`, xác thực mã băm SHA256, kiểm tra tính toàn vẹn đạt chuẩn `ok` trên toàn bộ 15 bảng cơ sở dữ liệu.
6. **Bộ kiểm thử hồi quy toàn diện**:
   - **102/102 unit & integration tests PASSED (100%)** (bao gồm 17 test tích hợp mới của R2).
   - **4/4 Playwright browser E2E tests PASSED (100%)**.
   - **Frontend production build thành công 100%** không lỗi cú pháp hay TypeScript.

---

## 2. PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ VÀ GIẢI PHÁP KỸ THUẬT R2

### 2.1. Bộ điều tiết đăng nhập đa chiều và chống Bot (Priority P0)

- **Khiếm khuyết ở R1:** Logic giới hạn tỷ lệ đăng nhập ở R1 chỉ áp dụng trên khóa kết hợp `(ip_address, username)` với ngưỡng 5 lần. Kẻ tấn công sử dụng botnet đổi IP liên tục có thể brute-force vô hạn một tài khoản mục tiêu; ngược lại, kẻ tấn công từ 1 IP có thể thử 4 mật khẩu trên hàng trăm tài khoản khác nhau (credential spraying) mà không bao giờ bị kích hoạt khóa.
- **Giải pháp xử lý tại `LoginProtectionService` & `apps/server/src/config.py`:**
  - **Tầng 1 (Pair Throttling):** $\ge 5$ lần thất bại trên cùng `(ip_address, username)` $\to$ Khóa cặp này trong 15 phút.
  - **Tầng 2 (Account Throttling):** $\ge 10$ lần thất bại trên cùng `username` (trên toàn bộ các IP nguồn) $\to$ Khóa tài khoản trên toàn hệ thống trong 15 phút, ngăn chặn brute-force phân tán.
  - **Tầng 3 (Source IP Throttling):** $\ge 20$ lần thất bại xuất phát từ cùng một `ip_address` (trên mọi tài khoản) $\to$ Khóa toàn bộ IP nguồn đó trong 15 phút, ngăn chặn credential spraying.
  - **Chống giả mạo IP (IP Spoofing Resistance):** Trích xuất IP trực tiếp từ kết nối mạng cấp thấp TCP socket (`request.client.host`). Tuyệt đối bỏ qua `X-Forwarded-For` khi chạy cục bộ chưa có reverse proxy tin cậy.
  - **Chống rò rỉ danh tính (Account Enumeration Resistance):** Trả về mã lỗi đồng nhất `401 Unauthorized` với chi tiết `"Incorrect username or password."` và mã `"INVALID_CREDENTIALS"` cho cả tài khoản không tồn tại lẫn tài khoản nhập sai mật khẩu.
  - **Được kiểm chứng bởi:** `tests/integration/test_phase5a_final_r2_security.py` (7/7 test passed).

---

### 2.2. Vòng đời đặt trước hạn ngạch nguyên tử (Quota Reservation Lifecycle)

- **Các nguy cơ tiềm ẩn:**
  - Tác vụ dài có thể chạy vượt quá thời hạn đặt trước ban đầu (30 phút) và bị cron thu hồi nhầm.
  - Worker bị phân mảnh mạng/treo máy (stale worker) sau khi bị thu hồi tài nguyên có thể cố ghi đè và làm sai lệch kế toán dung lượng.
  - Export dự án thất bại giữa chừng để lại tệp âm thanh dở dang trên ổ đĩa.
- **Giải pháp xử lý:**
  - **Gia hạn tự động qua Heartbeat (`renew_job_reservation`):** Mỗi khi worker gửi tín hiệu heartbeat (`DurableQueueService.heartbeat`), hạn ngạch đặt trước của job được tự động gia hạn thêm 1800 giây từ thời điểm hiện tại.
  - **Bảo vệ tác vụ đang hoạt động trong `cleanup_expired_reservations`:** Cơ chế dọn dẹp định kỳ chỉ thu hồi các reservation mồ côi hoặc của job đã bị hủy/chết; các job có trạng thái `QUEUED`, `PREPARING`, `RUNNING` và lease còn hiệu lực được bảo vệ tuyệt đối.
  - **Từ chối Worker trễ hạn với HTTP 409 (`RESERVATION_STALE_OR_RECLAIMED`):** Trong `commit_job_reservation`, nếu trạng thái của reservation không còn là `ACTIVE` (đã bị thu hồi hoặc quá hạn), giao dịch bị từ chối ngay lập tức, ngăn ngừa ghi nhận dữ liệu ma.
  - **Hủy bỏ tệp rác nguyên tử (`AudioDspService.export_project`):** Toàn bộ quy trình xuất âm thanh master được bọc trong khối `try ... except`. Khi gặp sự cố DSP hoặc lỗi đĩa, hệ thống giải phóng reservation ngay lập tức và thực hiện `unlink()` xóa sạch các tệp tạm (`tmp_output_file`, `final_output_file`).
  - **Được kiểm chứng bởi:** `tests/integration/test_phase5a_final_r2_quota_lifecycle.py` (6/6 test passed).

---

### 2.3. Phân tích thực nghiệm độ ưu tiên và hiện tượng bỏ đói (Priority Scheduling & Starvation)

- **Cơ chế hoạt động đã được kiểm chứng:**
  1. **Công bằng trong cùng cấp ưu tiên (Same Priority Tier):** Các tác vụ có cùng mức ưu tiên (ví dụ Priority 1) giữa các người dùng khác nhau được phân phối luân phiên theo cơ chế Round-Robin thời gian thực dựa trên `user_scheduling_states.last_dispatched_at`.
  2. **Ưu tiên nhảy cóc (Head-of-Line Priority Precedence):** Tác vụ có mức ưu tiên cao hơn (ví dụ Priority 10) luôn được đưa lên đầu hàng đợi và thực thi ngay trước toàn bộ các tác vụ có mức ưu tiên thấp hơn (Priority 1), bất kể thời gian nộp của tác vụ thấp hơn sớm hơn bao lâu.
  3. **Thực nghiệm nguy cơ bỏ đói (Starvation Risk):** Khi có một luồng tác vụ ưu tiên cao (Priority 10) liên tục nộp vào hệ thống, tác vụ ưu tiên thấp (Priority 1) buộc phải xếp hàng chờ cho đến khi toàn bộ tác vụ ưu tiên cao được xử lý hết.
- **Quyết định kiến trúc & Đánh đổi (Architecture Trade-offs):**
  - **Quyết định:** Không triển khai cơ chế "Priority Aging" (tự động tăng độ ưu tiên của job cũ theo thời gian).
  - **Lý do kỹ thuật và vận hành:** Trong môi trường phòng thu giọng nói chuyên nghiệp (Audio Studio), độ ưu tiên cao được phân bổ có chủ đích cho các tác vụ quan trọng khẩn cấp (Live Session preview, VIP export). Nếu áp dụng Priority Aging, các tác vụ dài nền (ví dụ audiobook 500 trang) sau một thời gian chờ sẽ tự động nhảy lên vượt quyền tác vụ khẩn cấp, làm phá vỡ SLA nghiệp vụ. Thay vào đó, nguy cơ starvation được kiểm soát thông qua hạn ngạch tài khoản `MAX_OUTSTANDING_JOBS_PER_USER = 25` và phân quyền nghiêm ngặt đối với quyền thiết lập Priority.
  - **Được kiểm chứng bởi:** `tests/integration/test_phase5a_final_r2_priority_fairness.py` (3/3 test passed).

---

### 2.4. Xử lý kịch bản dài tập tự trị (Autonomous Progressive Batch Processing)

- **Mục tiêu kiểm chứng:** Đảm bảo hệ thống có thể xử lý các kịch bản sách nói (Audiobook) lên tới 100 phân đoạn mà không phụ thuộc vào việc trình duyệt web của người dùng phải liên tục gửi request polling (`GET /projects`).
- **Kiến trúc luồng xử lý tự trị:**
  1. Khi người dùng nộp batch 100 phân đoạn, `ProjectService.render_batch` lập tức đưa 25 phân đoạn đầu tiên vào trạng thái `queued` và đánh dấu 75 phân đoạn còn lại là `pending` (không gây lỗi HTTP 429).
  2. Vòng lặp daemon của `DurableJobScheduler` định kỳ kích hoạt `ProjectService.reconcile_and_admit_pending_segments()`.
  3. Để triệt tiêu race condition giữa các luồng coroutine xử lý song song, triển khai **Admission Lock** nội bộ (`asyncio.Lock`) và gắn mã định danh **Idempotency Key duy nhất** cho từng phân đoạn (`seg-{segment_id}-{text_hash[:32]}`).
  4. Mỗi khi một tác vụ tổng hợp hoàn tất hoặc slot trống mở ra, hệ thống nền tự động đẩy các phân đoạn `pending` tiếp theo vào hàng đợi.
  5. **Kiểm chứng khả năng phục hồi sau thảm họa (Crash Resilience):**
     - Tại mốc hoàn thành 35 tác vụ: Mô phỏng khởi động lại tiến trình API (dispose kết nối DB pool).
     - Tại mốc hoàn thành 70 tác vụ: Mô phỏng dừng và khởi động lại tiến trình Runner Daemon.
     - Sau khi khôi phục: Quá trình tiếp diễn bình thường, toàn bộ 100/100 phân đoạn chuyển sang trạng thái `completed`, không phân đoạn nào bị kẹt ở `pending`, và tạo ra đúng 100 audio artifact độc bản duy nhất.
  6. **Được kiểm chứng bởi:** `tests/integration/test_phase5a_final_r2_autonomous_batch.py` (1/1 test passed).

---

## 3. KẾT QUẢ KIỂM THỬ TOÀN DIỆN (FULL REGRESSION MATRIX)

| Nhóm kiểm thử | Số lượng bài kiểm thử | Trạng thái | Thời gian thực thi |
| :--- | :--- | :--- | :--- |
| **Phase 5A Final Closure R2 Security Suite** | 7 tests | **PASS (100%)** | 1.80s |
| **Phase 5A Final Closure R2 Quota Lifecycle Suite** | 6 tests | **PASS (100%)** | 0.93s |
| **Phase 5A Final Closure R2 Priority Fairness Suite** | 3 tests | **PASS (100%)** | 8.15s |
| **Phase 5A Final Closure R2 Autonomous Batch Suite** | 1 test (100 segments) | **PASS (100%)** | 48.96s |
| **Toàn bộ Unit & Integration Test Suite** | 102 tests | **PASS (100%)** | 275.38s |
| **Playwright Browser E2E Test Suite** | 4 tests | **PASS (100%)** | ~58.10s |
| **Frontend Production Build (`apps/web`)** | 1 build | **PASS (100%)** | 20.35s |

---

## 4. BẰNG CHỨNG XÁC THỰC SAO LƯU TRỰC TUYẾN SQLITE (CLI BACKUP EVIDENCE)

Kiểm tra sao lưu được thực thi thông qua công cụ dòng lệnh tiêu chuẩn:
- **Lệnh tạo sao lưu:** `python -m apps.server.src.backup create`
- **Lệnh xác minh sao lưu:** `python -m apps.server.src.backup verify D:\AIVoiceStudioData\backups\studio_20261009_021229.db`

### Kết quả kiểm chứng chi tiết:
- **Đường dẫn tệp sao lưu:** `D:\AIVoiceStudioData\backups\studio_20261009_021229.db`
- **Dung lượng tệp:** `417,792 bytes`
- **Mã băm SHA256 chính xác:** `d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527`
- **Kiểm tra tính toàn vẹn (PRAGMA integrity_check):** `ok` (Quick check: `ok`)
- **Phiên bản di trú Alembic hiện tại:** `20261009_0006`
- **Tổng số bảng dữ liệu:** 15 bảng
- **Thống kê số dòng theo từng bảng:**
  - `users`: 14 rows
  - `engines`: 3 rows
  - `artifacts`: 36 rows
  - `jobs`: 38 rows
  - `alembic_version`: 1 rows
  - `job_events`: 290 rows
  - `reference_assets`: 0 rows
  - `projects`: 9 rows
  - `characters`: 2 rows
  - `script_segments`: 32 rows
  - `segment_revisions`: 4 rows
  - `project_exports`: 8 rows
  - `login_attempts`: 48 rows
  - `user_scheduling_states`: 0 rows
  - `storage_reservations`: 3 rows

---

## 5. MA TRẬN CÔ LẬP VÀ AN NINH VẬN HÀNH

- **Ràng buộc giao diện mạng:** `HOST = 127.0.0.1` (chỉ lắng nghe trên loopback cục bộ). Tuyệt đối không mở `0.0.0.0` hay cổng mạng LAN.
- **Chính sách CORS:** Giới hạn nghiêm ngặt tại `http://127.0.0.1:8765` và `http://127.0.0.1:5173`.
- **Cơ chế cách ly tệp âm thanh:** Mọi endpoint tải tệp âm thanh (`artifacts`, `exports`, `reference assets`) đều yêu cầu xác thực JWT qua Bearer Header tiêu chuẩn, nghiêm cấm đặt JWT trong query param.
- **Bảo toàn cơ sở hạ tầng:** Không thay đổi Windows Firewall, không cài đặt Caddy reverse proxy, không cấu hình Windows Services.

---

## 6. KẾT LUẬN VÀ NGHIỆM THU (FINAL VERDICT)

Milestone **Phase 5A** đã hoàn thành toàn diện các yêu cầu của **Final Closure R2**. Hệ thống vận hành ổn định, công bằng, bảo mật và hoàn toàn tự trị trên máy trạm cục bộ.

**QUYẾT NGHỊ: CHẤP THUẬN NGHIỆM THU HOÀN TOÀN (ACCEPTANCE PASS).**

*Lưu ý nghiêm ngặt:* Dừng toàn bộ hoạt động phát triển tại mốc này. **Không bắt đầu Phase 5B.**
