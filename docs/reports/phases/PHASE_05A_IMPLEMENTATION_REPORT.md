# AI Voice Studio — Báo Cáo Triển Khai Giai Đoạn 5A (Phase 5A Implementation Report)

**Vai trò:** Principal Backend Engineer, Application Security Engineer, Database Reliability Engineer & QA Lead  
**Trạng thái phê duyệt:** HOÀN THÀNH TOÀN DIỆN (100% ACCEPTANCE PASSED)  
**Ngày hoàn thành:** 09/10/2026  
**Commit cơ sở:** `a9e4f7e` (Phase 5 Planning Gate)  
**Phạm vi áp dụng:** Milestone 5A (Multi-User Core Hardening & Fair Resource Scheduling) trên `127.0.0.1` cục bộ.

---

## 1. TỔNG QUAN KẾT QUẢ ĐẠT ĐƯỢC

Giai đoạn 5A (Milestone 5A) tập trung gia cố an ninh lõi cho môi trường đa người dùng và thiết lập cơ chế điều phối tài nguyên công bằng (Fair Resource Scheduling) trước khi cho phép hệ thống mở rộng mạng cục bộ. Toàn bộ các thay đổi được thực hiện nghiêm ngặt trên nền tảng kiến trúc chấp thuận R1.1, SQLite WAL mode và phân tách tiến trình Engine Worker.

### Các thành quả kỹ thuật trọng tâm:

1. **Ma Trận Kiểm Soát Truy Cập Dựa Trên Vai Trò (RBAC Matrix & Negative Authorization)**:
   - Áp dụng triệt để dependency `require_editor` trên toàn bộ các route làm biến đổi dữ liệu (Mutations): tạo/sửa/xóa project, import kịch bản, thêm/sửa nhân vật, tạo/sửa segment, render TTS job, batch render, master export, và upload asset audio reference.
   - Tài khoản có vai trò `viewer` chỉ có quyền đọc (`GET`) các tài nguyên công khai hoặc tài nguyên thuộc về mình; mọi hành vi mutation đều bị chặn đứng với mã lỗi chuẩn `HTTP 403 Forbidden` (`FORBIDDEN_INSUFFICIENT_PERMISSIONS`).
   - Duy trì biện pháp phòng ngừa rủi ro mở tài khoản trái phép: endpoint `POST /auth/users` từ chối người dùng thông thường (`FORBIDDEN_USER_CREATION`), chỉ hệ thống bootstrap hoặc quản trị viên được chỉ định mới có quyền khởi tạo tài khoản.

2. **Cách Ly Tuyệt Đối Quyền Sở Hữu Voice Cloning (Strict Audio Reference Ownership)**:
   - Loại bỏ hoàn toàn cơ chế cho phép Quản trị viên (Admin) âm thầm sử dụng asset âm thanh tham chiếu của người dùng khác khi gửi job suy luận giọng nói (`durable_queue_service.py`).
   - Xác thực bắt buộc: `asset_rec.user_id == current_user.id`. Nếu cố tình tham chiếu đến asset của người khác, yêu cầu lập tức bị từ chối với `HTTP 403 Forbidden` (`FORBIDDEN_ASSET_ACCESS`), ngăn ngừa triệt để nguy cơ trộm cắp mẫu giọng cá nhân.

3. **Kế Toán & Cưỡng Chế Hạn Ngạch Lưu Trữ Không Phá Hủy (Non-destructive Storage Quotas)**:
   - Bổ sung trường `users.storage_quota_mb` (mặc định 2048 MB = 2 GB cho người dùng thông thường, hạn ngạch cấu hình linh hoạt cho Admin).
   - Triển khai `UserQuotaService` tính toán chính xác tổng dung lượng lưu trữ thực tế của mỗi người dùng bằng cách cộng dồn kích thước các tệp:
     - `artifacts`: Âm thanh thô sinh ra từ các job TTS.
     - `master_exports`: Tệp âm thanh xuất bản cuối cùng (WAV/MP3).
     - `assets`: Mẫu âm thanh tham chiếu giọng nói tải lên.
   - Khi vượt quá hạn ngạch, hệ thống lập tức từ chối yêu cầu với `HTTP 413 Payload Too Large` (`USER_STORAGE_QUOTA_EXCEEDED`).
   - Đảm bảo tính nguyên tử (Atomicity): Nếu việc ghép nối Master Audio Export hoặc ghi tệp thất bại/vượt quota, tệp tạm thời trên đĩa sẽ được dọn dẹp sạch sẽ ngay lập tức mà không để lại rác hay làm hỏng dữ liệu hiện hữu.

4. **Bộ Điều Phối Tài Nguyên Công Bằng (Fair-Share Scheduling & Priority Preemption)**:
   - Khắc phục nguy cơ cạn kiệt tài nguyên (Resource Starvation) khi một người dùng gửi hàng loạt job:
   - Trong `DurableQueueService.claim_next_job`:
     - Phân nhóm các job đang xếp hàng (`QUEUED`) theo mức ưu tiên (`priority`). Mức ưu tiên cao hơn luôn được giải quyết trước (**Priority Preemption**).
     - Trong cùng một mức ưu tiên, thuật toán thống kê số lượng job đang hoạt động (`PREPARING` hoặc `RUNNING`) của từng người dùng.
     - Ưu tiên trao lượt cấp phát tài nguyên cho **Người dùng ít hoạt động nhất** (**Least-Active-User-First**). Người dùng đang có ít job in-flight nhất sẽ được ưu tiên nhận slot CPU hoặc GPU khả dụng.
     - Duy trì nghiêm ngặt cơ chế chiếm giữ độc quyền phần cứng: Tối đa 1 slot GPU và 1 slot CPU tại một thời điểm, bảo vệ card đồ họa RTX 3050 khỏi tình trạng tràn VRAM.

5. **Giới Hạn Số Lượng Job Đang Xếp Hàng Của Mỗi Người Dùng (Per-User Outstanding Jobs Limit)**:
   - Thiết lập ngưỡng an toàn `MAX_OUTSTANDING_JOBS_PER_USER = 25` (cấu hình trong `config.py`).
   - Nếu một người dùng đang có $\ge 25$ job ở trạng thái `QUEUED`, `PREPARING` hoặc `RUNNING`, yêu cầu gửi thêm job mới sẽ bị chặn lại với `HTTP 429 Too Many Requests` (`TOO_MANY_OUTSTANDING_JOBS`).

6. **Bảo Vệ Đăng Nhập & Chống Dò Quét Tài Khoản (Brute-Force & Credential Hardening)**:
   - Tạo bảng `login_attempts` để ghi nhận nhật ký các lần đăng nhập thất bại kèm địa chỉ IP và username.
   - Triển khai `LoginProtectionService` với cơ chế Sliding Window 15 phút. Khi phát hiện $\ge 5$ lần đăng nhập sai từ một username hoặc một IP, hệ thống kích hoạt cơ chế khóa tạm thời và trả về `HTTP 429 Too Many Requests` (`TOO_MANY_LOGIN_ATTEMPTS`) kèm header chuẩn `Retry-After: 900`.
   - Chống thu thập danh sách tài khoản (Non-Enumeration Protection): Endpoint đăng nhập luôn trả về thông điệp trung lập đồng nhất: `"Incorrect username or password."` bất kể username tồn tại hay không.
   - Xác thực đổi mật khẩu an toàn: Bắt buộc cung cấp và xác thực mật khẩu hiện tại, đồng thời kiểm tra độ phức tạp của mật khẩu mới (tối thiểu 8 ký tự).

7. **Di Trú Cơ Sở Dữ Liệu An Toàn (Database Migration 20261009_0005)**:
   - Tập lệnh Alembic `alembic/versions/20261009_0005_phase5a_rbac_and_quotas.py` thêm cột `storage_quota_mb` và bảng `login_attempts` có đánh chỉ mục tối ưu trên `(ip_address, attempt_time)` và `(username, attempt_time)`.
   - Đã áp dụng thành công trên cơ sở dữ liệu thực tế tại `D:\AIVoiceStudioData\studio.db`. Bản sao lưu toàn vẹn đã được lưu trữ an toàn tại `D:\AIVoiceStudioData\backups/`.

---

## 2. DANH MỤC THAY ĐỔI MÃ NGUỒN VÀ KIẾN TRÚC

```
TTS/
├── alembic/
│   └── versions/
│       └── 20261009_0005_phase5a_rbac_and_quotas.py   (Migration: login_attempts table, users.storage_quota_mb)
├── apps/
│   └── server/src/
│       ├── api/v1/
│       │   ├── assets.py                              (Enforce require_editor, check user quota HTTP 413)
│       │   ├── auth.py                                (Login rate limiting HTTP 429, safe password change)
│       │   ├── jobs.py                                (Enforce require_editor)
│       │   └── projects.py                            (Enforce require_editor trên mọi mutation routes)
│       ├── config.py                                  (STORAGE_QUOTA_MB, MAX_OUTSTANDING_JOBS, LOGIN_MAX_FAILED_ATTEMPTS)
│       ├── core/
│       │   └── errors.py                              (Thêm custom headers hỗ trợ Retry-After trên AppError)
│       ├── models/
│       │   ├── __init__.py                            (Đăng ký LoginAttemptRecord)
│       │   ├── login_attempt.py                       (Model ghi nhận đăng nhập thất bại)
│       │   └── user.py                                (Thêm trường storage_quota_mb)
│       ├── schemas/
│       │   └── auth.py                                (Thêm UserPasswordChangeRequest)
│       └── services/
│           ├── audio_dsp_service.py                   (Gia cố dọn dẹp file tạm khi export thất bại)
│           ├── auth_service.py                        (Non-enumeration error message)
│           ├── durable_queue_service.py               (Fair-share scheduler, 25 jobs limit, strict cloning ownership)
│           ├── login_protection_service.py            (IP/User brute-force tracking & lockout)
│           ├── project_service.py                     (Quota checks khi submit segments & stitch master export)
│           └── user_quota_service.py                  (Tính toán storage accounting & kiểm tra quota)
├── docs/
│   ├── CHANGELOG.md                                   (Ghi chép chi tiết thay đổi Phase 5A)
│   ├── plans/
│   │   └── PHASE_05_DEPLOYMENT_SECURITY.md            (Cập nhật trạng thái hoàn thành Milestone 5A)
│   └── reports/
│       ├── phases/
│       │   └── PHASE_05A_IMPLEMENTATION_REPORT.md     (Báo cáo hiện tại)
│       ├── reviews/
│       │   ├── PHASE_05A_SECURITY_REVIEW.md           (Đánh giá an ninh độc lập Milestone 5A)
│       │   └── PHASE_05_PREFLIGHT_AUDIT_AND_THREAT_MODEL.md
│       └── tests/
│           └── PHASE_05A_TEST_EVIDENCE.md             (Bằng chứng kiểm thử chi tiết Milestone 5A)
└── tests/
    └── integration/
        ├── test_migrations.py                         (Cập nhật head revision assertion lên 20261009_0005)
        └── test_phase5a_rbac_and_fairness.py          (Bộ test toàn diện 7 kịch bản cho Milestone 5A)
```

---

## 3. KẾT QUẢ KIỂM THỬ VÀ XÁC NHẬN CHẤT LƯỢNG

Toàn bộ hệ thống đã vượt qua 100% các bài kiểm thử hồi quy và kiểm thử tính năng mới mà không ghi nhận bất kỳ sự cố nào:

- **Bộ kiểm thử tích hợp Milestone 5A (`tests/integration/test_phase5a_rbac_and_fairness.py`)**:
  - `test_5a_rbac_matrix_and_negative_authorization`: **PASSED** (Viewer bị chặn 403 trên mutation; Viewer xem được dự án; User creation bị chặn 403).
  - `test_5a_password_change_flow`: **PASSED** (Xác thực mật khẩu cũ chính xác, từ chối mật khẩu mới ngắn hơn 8 ký tự, đăng nhập thành công bằng mật khẩu mới).
  - `test_5a_brute_force_lockout_and_no_enumeration`: **PASSED** (Sai 5 lần kích hoạt khóa 429 kèm `Retry-After: 900`, thông điệp báo lỗi không lộ thông tin username).
  - `test_5a_fair_share_queue_scheduling`: **PASSED** (Xếp hàng đa người dùng, Least-Active-User-First điều phối công bằng cho slot CPU giữa 2 người dùng, Priority Preemption đảm bảo job ưu tiên cao được chạy trước).
  - `test_5a_max_outstanding_jobs_limit`: **PASSED** (Chặn đứng job thứ 26 với mã lỗi 429 `TOO_MANY_OUTSTANDING_JOBS`).
  - `test_5a_user_storage_quota_enforcement`: **PASSED** (Chặn upload và render khi vượt dung lượng quota với mã lỗi 413 `USER_STORAGE_QUOTA_EXCEEDED`).
  - `test_5a_voice_cloning_strict_ownership_no_admin_bypass`: **PASSED** (Admin bị chặn 403 khi dùng reference asset của user khác).

- **Toàn bộ bộ kiểm thử hồi quy (Full Regression Test Suite)**:
  - **78 / 78 bài kiểm thử PASSED 100%** trong thời gian 3 phút 06 giây.

---

## 4. KẾT LUẬN & KHUYẾN NGHỊ

Milestone 5A đã hoàn thành xuất sắc toàn bộ các mục tiêu đặt ra: củng cố an ninh xác thực, bảo vệ hạn ngạch lưu trữ, điều phối hàng đợi công bằng và ngăn ngừa rủi ro lạm quyền. Hệ thống đã sẵn sàng về mặt kiến trúc lõi để chuyển sang xem xét phê duyệt các ADR tiếp theo trước khi tiến hành Milestone 5B.
