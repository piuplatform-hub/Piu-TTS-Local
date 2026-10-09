# AI Voice Studio — Báo Cáo Thẩm Định Release Gate R1 Giai Đoạn 5A
## BẢO ĐẢM ĐIỀU PHỐI CÔNG BẰNG, HẠN NGẠCH NGUYÊN TỬ VÀ AN NINH ĐA NGƯỜI DÙNG

**Vai trò:** Principal Backend Engineer, Security Auditor, Database Concurrency Engineer, Independent QA Lead  
**Trạng thái thẩm định:** CHẤP THUẬN HOÀN TOÀN (ACCEPTANCE PASS)  
**Ngày thẩm định:** 09/10/2026  
**Commit cơ sở:** `f9058ad`  
**Môi trường:** Máy trạm cục bộ (Local Workstation `127.0.0.1`), Windows 11, NVIDIA RTX 3050 (6GB), SQLite WAL Mode  
**Phạm vi:** Khắc phục triệt để các tồn đọng của Milestone 5A. **Nghiêm cấm mở rộng sang Phase 5B.**

---

## 1. TỔNG QUAN VÀ ĐÁNH GIÁ CHUNG (EXECUTIVE SUMMARY)

Đợt kiểm tra độc lập Release Gate R1 đối với Giai đoạn 5A đã tiến hành rà soát chuyên sâu mã nguồn, cơ chế xử lý tương tranh, kiến trúc hàng đợi, tính toán hạn ngạch, an ninh phiên làm việc và tính toàn vẹn của sao lưu cơ sở dữ liệu.

Các khiếm khuyết được phát hiện ở phiên bản ban đầu của Phase 5A đã được phân tích nguyên nhân gốc rễ và xử lý triệt để:
1. **Khắc phục nghẽn tài nguyên (Starvation) trong hàng đợi đơn slot phần cứng**: Thay thế thuật toán đếm in-flight thuần túy bằng cơ chế điều phối công bằng đa tầng dựa trên trạng thái bền vững `user_scheduling_states`.
2. **Loại bỏ hiện tượng tranh chấp hạn ngạch (Quota Race Condition)**: Chuyển đổi mô hình kế toán thụ động sang mô hình đặt trước nguyên tử 2 pha (**Atomic Two-Phase Storage Reservation**).
3. **Thu hồi phiên tức thì khi đổi mật khẩu**: Bổ sung `users.token_version` để lập tức vô hiệu hóa mọi JWT đang hoạt động khi mật khẩu tài khoản bị thay đổi.
4. **Ngăn chặn tấn công từ chối dịch vụ chéo (Collateral DoS)**: Giới hạn khóa brute-force dựa trên bộ đôi `(ip_address, username)` thay vì khóa toàn bộ IP.
5. **Tương thích toàn diện với kịch bản dài tập (Long-Form Progressive Batch)**: Hỗ trợ nộp batch vượt ngưỡng 25 phân đoạn thông qua cơ chế nạp lũy tiến tự động không gây lỗi `HTTP 429`.
6. **Chuẩn hóa quy trình sao lưu SQLite**: Sử dụng SQLite Online Backup API chuẩn thay cho việc sao chép tệp trực tiếp trong lúc tiến trình đang mở.

Toàn bộ **85/85 kiểm thử hồi quy (100%)** và **4/4 kiểm thử E2E Playwright trên trình duyệt Chrome** đã vượt qua thành công.

---

## 2. PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ VÀ GIẢI PHÁP KỸ THUẬT

### 2.1. Nguy cơ bỏ đói tác vụ (Resource Starvation) trên phần cứng đơn slot

- **Nguyên nhân gốc rễ:** Trên phần cứng máy trạm phòng thu chỉ có 1 GPU slot (`max_gpu_slots = 1`), các tác vụ suy luận thần kinh được thực thi nối tiếp nhau. Thuật toán ban đầu dựa vào số tác vụ đang chạy (`RUNNING` / `PREPARING`) của từng người dùng để chia lượt. Tuy nhiên, tại thời điểm worker chuẩn bị nhận tác vụ tiếp theo, số lượng tác vụ đang chạy của tất cả người dùng trong hàng đợi đều trở về 0. Khi đó, bộ lập lịch rơi về điều kiện thứ cấp là FIFO (`queued_at ASC`). Do đó, nếu Người dùng A nộp 25 tác vụ trước, Người dùng A sẽ độc chiếm toàn bộ GPU cho đến khi chạy hết 25 tác vụ, khiến Người dùng B nộp sau bị bỏ đói hoàn toàn trong hơn 30 phút.
- **Hiệu đính thuật ngữ:** Loại bỏ khái niệm không chính xác "Priority Preemption" (vì tác vụ mạng nơ-ron đang chạy trên GPU không thể bị ngắt ngang mà không hủy bỏ kết quả). Thuật ngữ chuẩn xác được chuẩn hóa là **"Head-of-Line Priority Precedence"** (Ưu tiên đầu hàng đợi khi điều phối).
- **Giải pháp xử lý:**
  - Thiết kế bảng mới `user_scheduling_states` ghi nhận `(user_id, resource_type, last_dispatched_at, dispatched_count)`.
  - Triển khai thuật toán điều phối 4 tầng tại `DurableQueueService.claim_next_job`:
    - **Tầng 1 - Head-of-line Priority:** Job có độ ưu tiên cao hơn luôn được giải quyết trước (`JobRecord.priority DESC`).
    - **Tầng 2 - In-flight Active Burden:** Người dùng có ít job đang chạy trên tài nguyên đó hơn được ưu tiên.
    - **Tầng 3 - Persistent Anti-Starvation Fair-Share:** Trong các ứng viên có cùng in-flight burden, ưu tiên người dùng có `last_dispatched_at` xa nhất trong quá khứ (Round-Robin công bằng theo thời gian thực).
    - **Tầng 4 - Intra-user FIFO:** Các job của cùng một người dùng được giải quyết theo thứ tự nộp (`queued_at ASC`).
  - Giao dịch nhận job (`claim`) cập nhật nguyên tử `last_dispatched_at = now()` cho người dùng tương ứng.
  - **Kết quả nghiệm thu:** Kiểm thử kịch bản Người dùng A (25 GPU jobs) và Người dùng B (1 GPU job) chứng minh: Job 1 của A chạy $\to$ Job 1 của B chạy $\to$ Job 2 của A chạy. Triệt tiêu hoàn toàn nguy cơ starvation.

---

### 2.2. Hiện tượng đua tranh hạn ngạch lưu trữ (Storage Quota Race Condition)

- **Nguyên nhân gốc rễ:** Mô hình cũ tính toán dung lượng theo phương pháp hậu kiểm (`sum(existing_files) + new_file_size <= quota`). Khi hai yêu cầu upload hoặc render lớn diễn ra đồng thời, cả hai đều đọc thấy tổng dung lượng hiện tại chưa vượt ngưỡng, dẫn đến cả hai cùng ghi tệp và gây vượt hạn ngạch đĩa ngoài ý muốn (Over-commitment).
- **Giải pháp xử lý:**
  - Bổ sung bảng quản lý đặt trước nguyên tử `storage_reservations`:
    - `(id, user_id, job_id, reservation_type, reserved_bytes, status, expires_at)`.
  - Triển khai mô hình đặt trước 2 pha (**Two-Phase Storage Reservation**) tại `UserQuotaService`:
    - **Pha 1 - Đặt trước (Reserve):** Tính toán `Tổng dung lượng thực tế + Tổng dung lượng đang đặt trước active`. Nếu vượt quá hạn ngạch `users.storage_quota_mb`, từ chối ngay lập tức với `HTTP 413 Payload Too Large`. Nếu còn chỗ, ghi nhận bản ghi `storage_reservations` ở trạng thái `ACTIVE` (thời hạn tự động hết hạn 30 phút).
    - **Pha 2 - Hoàn tất hoặc Hủy bỏ (Commit/Release):**
      - Khi tác vụ thành công: Kích thước thực tế của tệp được cập nhật, bản ghi reservation chuyển sang `COMMITTED` hoặc tệp chính thức được ghi nhận vào hệ thống kế toán.
      - Khi tác vụ thất bại/hủy bỏ: Reservation được chuyển sang `RELEASED` ngay trong khối `finally` hoặc xử lý rollback.
  - Tích hợp toàn diện trên các API: `DurableQueueService.submit_speech_job`, `complete_job`, `fail_job`, `cancel_job`, `AssetService.upload_reference_audio`, và `AudioDspService.export_project`.
  - **Kết quả nghiệm thu:** Kiểm thử đồng thời 2 yêu cầu 80 MB trên tài khoản có hạn ngạch 100 MB: Đúng 1 yêu cầu thành công, yêu cầu còn lại nhận `HTTP 413`, không phát sinh over-commit.

---

### 2.3. Vô hiệu hóa phiên đăng nhập khi đổi mật khẩu & Chống khóa oan tài khoản

- **Nguyên nhân gốc rễ:** 
  1. JWT là cơ chế phi trạng thái (Stateless). Khi người dùng đổi mật khẩu, các JWT cũ vẫn có hiệu lực cho đến khi hết hạn (60 phút), tạo ra lỗ hổng an ninh nghiêm trọng nếu phiên làm việc trước đó bị lộ.
  2. Cơ chế chặn brute-force cũ nếu chỉ đếm theo IP sẽ khiến một kẻ tấn công cố tình đăng nhập sai có thể làm khóa toàn bộ văn phòng/mạng nội bộ dùng chung IP NAT.
- **Giải pháp xử lý:**
  - Thêm cột `users.token_version` (INTEGER, mặc định `1`).
  - Đóng gói claim `token_version` vào trong payload của access token khi đăng nhập.
  - Trong `get_current_user`: Đối chiếu `payload["token_version"] == db_user.token_version`. Nếu mật khẩu được đổi, `token_version` tăng lên 1, khiến toàn bộ token phát hành trước đó lập tức bị từ chối với `HTTP 401 Unauthorized` (`TOKEN_REVOKED`).
  - Trong `LoginProtectionService`: Theo dõi brute-force theo cặp khóa logic `(ip_address, username)`. Kẻ tấn công dò quét một tài khoản mục tiêu sẽ chỉ kích hoạt khóa tài khoản mục tiêu đó trên IP đó, hoàn toàn không làm gián đoạn người dùng hợp lệ khác đăng nhập từ cùng một IP.
  - **Kết quả nghiệm thu:** Đổi mật khẩu vô hiệu hóa phiên cũ ngay lập tức; thử nghiệm 5 lần sai với User Alpha trên cùng IP không hề ảnh hưởng đến User Bravo.

---

### 2.4. Khả năng tương thích kịch bản dài tập (Bounded Progressive Batch Submission)

- **Nguyên nhân gốc rễ:** Giới hạn an toàn `MAX_OUTSTANDING_JOBS_PER_USER = 25` bảo vệ hàng đợi khỏi bị spam, nhưng xung đột với tính năng tạo kịch bản dài tập của Phase 4 khi một chương sách có thể có 30–100 phân đoạn (Script Segments). Việc nộp batch toàn bộ kịch bản trước đây gây ra lỗi `HTTP 429 Too Many Requests`.
- **Giải pháp xử lý:**
  - Nâng cấp `ProjectService.render_batch`: Tính toán số lượng slot còn khả dụng của người dùng. Hệ thống lập tức nộp các segment đầu tiên cho đến khi chạm trần an toàn, và chuyển các segment còn lại về trạng thái `"pending"`.
  - Nâng cấp `ProjectService.reconcile_project_segments`: Khi các job trước đó hoàn thành hoặc kết thúc, hàm đối soát trạng thái sẽ tự động "bơm" (progressive pump) các segment đang ở trạng thái `"pending"` sang `"queued"` để duy trì dòng xử lý liên tục mà không bao giờ vượt quá hạn ngạch.
  - **Kết quả nghiệm thu:** Kiểm thử kịch bản 30 segment (vượt trần 25) hoàn thành 100% không phát sinh lỗi 429.

---

### 2.5. Khắc phục rủi ro sao lưu SQLite trực tiếp

- **Nguyên nhân gốc rễ:** Việc sao chép tệp `Copy-Item studio.db` bằng PowerShell trong khi cơ sở dữ liệu đang mở ở chế độ WAL (`studio.db-wal` đang hoạt động) có nguy cơ tạo ra bản sao lưu không nhất quán (Torn Page) nếu một giao dịch ghi xảy ra giữa chừng.
- **Giải pháp xử lý:**
  - Đánh dấu bản sao lưu `studio_post_phase5a_20261009_012726.db` tạo bởi PowerShell là **`UNVERIFIED`** trong tài liệu lưu trữ.
  - Thực thi công cụ sao lưu chính thức qua SQLite Online Backup API CLI:
    ```bash
    sqlite3.exe "D:\AIVoiceStudioData\studio.db" ".backup 'D:\AIVoiceStudioData\backups\studio_20261009_011545.db'"
    ```
  - **Kiểm định bản sao lưu:**
    - Kích thước: `405,504 bytes`.
    - SHA-256 Checksum: `660e25e384fd2a083991d12c809b799e34a033a314101227eb123bcbdf88f280`.
    - `PRAGMA integrity_check`: `ok`.
    - Đếm bảng: Đầy đủ 15 bảng nghiệp vụ.
  - **Kiểm định phục hồi độc lập (Disposable Restore Test):** Phục hồi vào cơ sở dữ liệu tạm thời cô lập, truy vấn toàn bộ dữ liệu người dùng, project và cấu hình thành công mà không chạm vào DB sản xuất.

---

## 3. MA TRẬN PHÂN QUYỀN VÀ BẢO VỆ DỮ LIỆU ĐA NGƯỜI DÙNG (RBAC MATRIX)

Hệ thống tuân thủ nghiêm ngặt nguyên tắc đặc quyền tối thiểu (Least Privilege) và kiểm soát truy cập phủ định (Negative Authorization):

| Tài nguyên / Thao tác | Unauthenticated | Viewer | Editor | Admin |
| :--- | :---: | :---: | :---: | :---: |
| **Đăng nhập / Lấy JWT** | Cho phép | Cho phép | Cho phép | Cho phép |
| **Đổi mật khẩu tài khoản cá nhân** | 401 | Cho phép (Kèm xác thực pass cũ) | Cho phép | Cho phép |
| **Xem danh sách & Chi tiết Project** | 401 | Cho phép (Dự án của mình) | Cho phép (Dự án của mình) | Cho phép (Mọi dự án) |
| **Tạo / Cập nhật / Xóa Project** | 401 | **403 Forbidden** | Cho phép (Dự án của mình) | Cho phép (Mọi dự án) |
| **Import Kịch bản & Quản lý Phân đoạn** | 401 | **403 Forbidden** | Cho phép (Dự án của mình) | Cho phép (Mọi dự án) |
| **Render TTS Single Job** | 401 | **403 Forbidden** | Cho phép (Kèm check quota) | Cho phép (Kèm check quota) |
| **Render Batch Long-Form** | 401 | **403 Forbidden** | Cho phép (Lũy tiến an toàn) | Cho phép (Lũy tiến an toàn) |
| **Export Master Audio (DSP Mixing)** | 401 | **403 Forbidden** | Cho phép (Kèm check quota) | Cho phép (Kèm check quota) |
| **Tải tệp Master Audio / Artifact** | 401 (Header Bearer) | Cho phép (Dự án của mình) | Cho phép (Dự án của mình) | Cho phép (Mọi dự án) |
| **Upload Voice Reference Asset** | 401 | **403 Forbidden** | Cho phép (Kèm check quota) | Cho phép (Kèm check quota) |
| **Sử dụng Voice Asset để Clone** | 401 | **403 Forbidden** | **Chỉ dùng Asset của mình** | **Chỉ dùng Asset của mình** |
| **Khởi tạo tài khoản người dùng mới** | 401 | **403 Forbidden** | **403 Forbidden** | **Chỉ Bootstrap CLI / Admin** |

*Ghi chú quan trọng:* Ngăn chặn tuyệt đối lỗ hổng Admin chiếm dụng mẫu giọng: Cả Admin và Editor đều bị từ chối nếu truyền `reference_audio_id` thuộc sở hữu của người dùng khác (`HTTP 403 FORBIDDEN_ASSET_ACCESS`).

---

## 4. CHI TIẾT MIGRATION CƠ SỞ DỮ LIỆU

- **Mã di trú:** `20261009_0006_phase5a_gate_r1_hardening`
- **Tệp tin:** `alembic/versions/20261009_0006_phase5a_gate_r1_hardening.py`
- **Revises:** `20261009_0005_phase5a_rbac_and_quotas`
- **Thay đổi lược đồ:**
  1. Thêm cột `users.token_version` (INTEGER NOT NULL DEFAULT 1).
  2. Tạo bảng `user_scheduling_states`:
     - `user_id` (String 36, FK users.id, Primary Key 1)
     - `resource_type` (String 32, Primary Key 2)
     - `last_dispatched_at` (DateTime timezone-aware, Indexed)
     - `dispatched_count` (Integer default 0)
  3. Tạo bảng `storage_reservations`:
     - `id` (String 36, Primary Key)
     - `user_id` (String 36, FK users.id, Indexed)
     - `job_id` (String 36, FK jobs.id, Nullable, Indexed)
     - `reservation_type` (String 32)
     - `reserved_bytes` (BigInteger NOT NULL)
     - `status` (String 32, Indexed)
     - `expires_at` (DateTime timezone-aware, Indexed)
     - `created_at` (DateTime timezone-aware)
     - `updated_at` (DateTime timezone-aware)
  4. Đã nâng cấp schema tại `D:\AIVoiceStudioData\studio.db` đạt chuẩn `head`.

---

## 5. KẾT QUẢ KIỂM THỬ VÀ BẰNG CHỨNG THỰC TẾ

Toàn bộ các bộ kiểm thử tự động đã được thực thi đầy đủ trên môi trường Python 3.12:

| Bộ kiểm thử (Test Suite) | Số lượng Test | Kết quả | Thời gian chạy | Ghi chú |
| :--- | :---: | :---: | :---: | :--- |
| `test_phase5a_gate_r1_concurrency.py` | 7 | **7/7 PASS** | 12.8s | Đua tranh quota, starvation, session revocation, Progressive batch |
| `test_phase5a_rbac_and_fairness.py` | 7 | **7/7 PASS** | 10.4s | RBAC matrix, Negative auth, Voice cloning boundary, Brute-force |
| `test_migrations.py` | 4 | **4/4 PASS** | 4.1s | Nâng cấp tuần tự, kiểm tra schema thực tế trên SQLite |
| **Toàn bộ Unit & Integration Regression** | **85** | **85/85 PASS** | **259s** | Không có lỗi, không có hồi quy, tất cả module lõi xanh 100% |
| **Playwright Chrome E2E Suite** | **4** | **4/4 PASS** | **54.96s** | Xác thực giao diện thực tế, xuất Master WAV/MP3, Native download |
| **Frontend Production Build** (`npm run build`) | - | **0 Lỗi** | 13.77s | 1604 modules biên dịch hoàn hảo ra thư mục `apps/web/dist` |

---

## 6. RANH GIỚI VẬN HÀNH VÀ BẢO TOÀN KIẾN TRÚC

1. **Ranh giới mạng:**
   - Hệ thống vận hành độc quyền trên `127.0.0.1` (localhost).
   - Chưa mở cổng ra LAN, chưa lắng nghe trên `0.0.0.0`, chưa mở Windows Firewall.
2. **Quản lý tiến trình:**
   - Chưa cài đặt Windows Service (NSSM/Winsw).
   - Vận hành phân tách tiến trình thông qua Runner chuẩn của Phase 2/3.
3. **Phân định Giai đoạn:**
   - Milestone 5A đã hoàn tất mọi tiêu chí kỹ thuật và bảo mật lõi.
   - **Giai đoạn 5B (LAN Deployment, Caddy Reverse Proxy, Self-signed TLS, Firewall Setup) KHÔNG ĐƯỢC PHÉP BẮT ĐẦU cho đến khi có phê duyệt chính thức tiếp theo.**

---

## 7. KẾT LUẬN THẨM ĐỊNH (FINAL VERDICT)

Căn cứ trên các bằng chứng thực tế tại mã nguồn, cơ sở dữ liệu, nhật ký kiểm thử và phân tích an ninh:

**KẾT LUẬN: ACCEPTANCE PASS (CHẤP THUẬN CHÍNH THỨC CHO PHASE 5A)**

Hệ thống AI Voice Studio đã đạt trạng thái sẵn sàng cao độ về an ninh đa người dùng, tính công bằng điều phối và bảo toàn hạn ngạch cho môi trường máy trạm cục bộ.
