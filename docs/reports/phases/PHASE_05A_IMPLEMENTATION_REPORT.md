# AI Voice Studio — Báo Cáo Triển Khai Giai Đoạn 5A (Phase 5A Implementation Report)
## BẢO VỆ ĐA NGƯỜI DÙNG, ĐIỀU PHỐI CÔNG BẰNG & KHẮC PHỤC RELEASE GATE R1

**Vai trò:** Principal Backend Engineer, Application Security Engineer, Database Concurrency Engineer & QA Lead  
**Trạng thái phê duyệt:** HOÀN THÀNH TOÀN DIỆN & ĐẠT RELEASE GATE R1 (ACCEPTANCE PASS)  
**Ngày hoàn thành:** 09/10/2026  
**Commit cơ sở:** `a9e4f7e` (Phase 5 Planning Gate) $\to$ `f9058ad` (Phase 5A Initial) $\to$ Release Gate R1 Remediation  
**Phạm vi áp dụng:** Milestone 5A (Multi-User Core Hardening & Fair Resource Scheduling) trên `127.0.0.1` cục bộ.

---

## 1. TỔNG QUAN KẾT QUẢ ĐẠT ĐƯỢC

Giai đoạn 5A (Milestone 5A) tập trung gia cố an ninh lõi cho môi trường đa người dùng và thiết lập cơ chế điều phối tài nguyên công bằng (Fair Resource Scheduling) trước khi cho phép hệ thống mở rộng mạng cục bộ. Toàn bộ các thay đổi được thực hiện nghiêm ngặt trên nền tảng kiến trúc chấp thuận R1.1, SQLite WAL mode và phân tách tiến trình Engine Worker.

Sau đợt rà soát độc lập Release Gate R1, toàn bộ các khiếm khuyết tương tranh và góc khuất an ninh đã được khắc phục triệt để.

### Các thành quả kỹ thuật trọng tâm:

1. **Ma Trận Kiểm Soát Truy Cập Dựa Trên Vai Trò (RBAC Matrix & Negative Authorization)**:
   - Áp dụng triệt để dependency `require_editor` trên toàn bộ các route làm biến đổi dữ liệu (Mutations): tạo/sửa/xóa project, import kịch bản, thêm/sửa nhân vật, tạo/sửa segment, render TTS job, batch render, master export, và upload asset audio reference.
   - Tài khoản có vai trò `viewer` chỉ có quyền đọc (`GET`) các tài nguyên thuộc về mình; mọi hành vi mutation đều bị chặn đứng với mã lỗi chuẩn `HTTP 403 Forbidden` (`FORBIDDEN_INSUFFICIENT_PERMISSIONS`).
   - Duy trì biện pháp phòng ngừa rủi ro mở tài khoản trái phép: endpoint `POST /auth/users` từ chối người dùng thông thường (`FORBIDDEN_USER_CREATION`), chỉ hệ thống bootstrap hoặc quản trị viên được chỉ định mới có quyền khởi tạo tài khoản.

2. **Cách Ly Tuyệt Đối Quyền Sở Hữu Voice Cloning (Strict Audio Reference Ownership)**:
   - Loại bỏ hoàn toàn cơ chế cho phép Quản trị viên (Admin) âm thầm sử dụng asset âm thanh tham chiếu của người dùng khác khi gửi job suy luận giọng nói (`durable_queue_service.py`).
   - Xác thực bắt buộc: `asset_rec.user_id == current_user.id`. Nếu cố tình tham chiếu đến asset của người khác, yêu cầu lập tức bị từ chối với `HTTP 403 Forbidden` (`FORBIDDEN_ASSET_ACCESS`), ngăn ngừa triệt để nguy cơ trộm cắp mẫu giọng cá nhân.

3. **Kế Toán & Đặt Trước Hạn Ngạch Lưu Trữ Nguyên Tử (Atomic Two-Phase Storage Quota Reservation)**:
   - Bổ sung trường `users.storage_quota_mb` (mặc định 2048 MB = 2 GB cho người dùng thông thường, cấu hình linh hoạt cho Admin).
   - Khắc phục triệt để rủi ro đua tranh vượt hạn ngạch (Race Condition Over-commit) bằng bảng `storage_reservations` và cơ chế đặt trước 2 pha trong `UserQuotaService`:
     - **Pha 1 (Reserve):** Khi tiếp nhận yêu cầu (submit TTS job, upload audio asset, xuất bản master export), hệ thống tính toán `Tổng dung lượng thực tế + Tổng dung lượng đang đặt trước active`. Nếu vượt hạn ngạch, từ chối ngay với `HTTP 413 Payload Too Large` (`USER_STORAGE_QUOTA_EXCEEDED`). Nếu còn chỗ, ghi nhận bản ghi reservation `ACTIVE` với thời hạn tự hủy an toàn.
     - **Pha 2 (Commit / Release):** Khi tác vụ thành công, chuyển reservation sang `COMMITTED` hoặc cập nhật kích thước tệp thực tế; khi thất bại hoặc bị hủy bỏ, lập tức giải phóng (`RELEASED`) trong khối `finally` hoặc rollback.
   - Đảm bảo tính nguyên tử: Dọn dẹp sạch sẽ các tệp tạm thời trên đĩa khi phát sinh lỗi mà không làm ảnh hưởng dữ liệu hiện hữu.

4. **Bộ Điều Phối Tài Nguyên Công Bằng Đa Tầng (4-Tier Anti-Starvation Fair-Share Scheduling)**:
   - Khắc phục nguy cơ cạn kiệt tài nguyên (Resource Starvation) khi chỉ có 1 GPU slot (`max_gpu_slots = 1`) bằng bảng trạng thái bền vững `user_scheduling_states`:
   - Chuẩn hóa thuật ngữ: Thay thế "Priority Preemption" bằng **"Head-of-Line Priority Precedence"** (Ưu tiên đầu hàng đợi khi điều phối) vì mạng nơ-ron đang chạy không thể bị ngắt ngang.
   - Thuật toán điều phối 4 tầng trong `DurableQueueService.claim_next_job`:
     - **Tầng 1 (Priority):** Ưu tiên mức độ quan trọng (`JobRecord.priority DESC`).
     - **Tầng 2 (In-flight Burden):** Ưu tiên người dùng có ít job đang chạy trên tài nguyên đó hơn.
     - **Tầng 3 (Persistent Anti-Starvation):** Ưu tiên người dùng có `last_dispatched_at` xa nhất trong quá khứ (Round-Robin công bằng giữa các người dùng).
     - **Tầng 4 (FIFO):** Thứ tự nộp job theo thời gian (`queued_at ASC`).
   - Duy trì giới hạn chiếm giữ độc quyền: Tối đa 1 slot GPU và 1 slot CPU tại một thời điểm, bảo vệ GPU RTX 3050 khỏi tràn VRAM.

5. **Tương Thích Kịch Bản Dài Tập (Bounded Progressive Batch Submission)**:
   - Duy trì giới hạn bảo vệ hàng đợi `MAX_OUTSTANDING_JOBS_PER_USER = 25`.
   - Nâng cấp `ProjectService.render_batch` và `reconcile_project_segments`: Cho phép người dùng nộp batch dài tập (ví dụ 30–100 phân đoạn). Hệ thống tự động nộp tối đa slot cho phép và chuyển các phân đoạn còn lại thành `"pending"`. Khi các job trước đó hoàn thành, các phân đoạn pending sẽ được tự động "bơm" (progressive pump) vào hàng đợi mà không phát sinh lỗi `HTTP 429`.

6. **Bảo Vệ Đăng Nhập & Thu Hồi Phiên Tức Thì (Session Invalidation & Brute-Force Hardening)**:
   - Thêm cột `users.token_version` (INTEGER). Khi đổi mật khẩu, `token_version` tăng lên, toàn bộ JWT phát hành trước đó lập tức bị vô hiệu hóa với `HTTP 401 Unauthorized` (`TOKEN_REVOKED`).
   - `LoginProtectionService` theo dõi các lần đăng nhập sai theo cặp `(ip_address, username)`. Nếu một tài khoản bị dò quét sai 5 lần trên 1 IP, tài khoản đó bị khóa tạm thời (`HTTP 429` kèm `Retry-After: 900`), trong khi các tài khoản khác trên cùng IP không bị ảnh hưởng (chống tấn công Collateral DoS).
   - Bảo vệ chống user enumeration bằng thông điệp trung lập đồng nhất: `"Incorrect username or password."`.

7. **Di Trú Cơ Sở Dữ Liệu An Toàn & Chuẩn Hóa Sao Lưu SQLite**:
   - Áp dụng thành công migration `20261009_0005_phase5a_rbac_and_quotas.py` và `20261009_0006_phase5a_gate_r1_hardening.py` trên `D:\AIVoiceStudioData\studio.db`.
   - Chuẩn hóa quy trình sao lưu bằng SQLite Online Backup API CLI: Tệp sao lưu `D:\AIVoiceStudioData\backups\studio_20261009_011545.db` (405,504 bytes, SHA-256: `660e25e384fd2a083991d12c809b799e34a033a314101227eb123bcbdf88f280`, `PRAGMA integrity_check = ok`, đủ 15 bảng).
   - Đã kiểm tra phục hồi độc lập thành công trên cơ sở dữ liệu tạm thời (Disposable Restore Test). Bản sao lưu cũ bằng PowerShell `Copy-Item` đã được đánh dấu rõ ràng là `UNVERIFIED`.

---

## 2. DANH MỤC THAY ĐỔI MÃ NGUỒN VÀ KIẾN TRÚC

```
TTS/
├── alembic/
│   └── versions/
│       ├── 20261009_0005_phase5a_rbac_and_quotas.py           (login_attempts table, users.storage_quota_mb)
│       └── 20261009_0006_phase5a_gate_r1_hardening.py        (user_scheduling_states, storage_reservations, users.token_version)
├── apps/
│   └── server/src/
│       ├── api/v1/
│       │   ├── assets.py                                      (require_editor, user quota check HTTP 413, atomic reservation)
│       │   ├── auth.py                                        (Login rate limiting HTTP 429, safe password change, token_version)
│       │   ├── jobs.py                                        (require_editor)
│       │   └── projects.py                                    (require_editor trên mọi mutation routes)
│       ├── config.py                                          (STORAGE_QUOTA_MB, MAX_OUTSTANDING_JOBS, LOGIN_MAX_FAILED_ATTEMPTS)
│       ├── core/
│       │   └── errors.py                                      (Hỗ trợ custom headers Retry-After trên AppError)
│       ├── models/
│       │   ├── __init__.py                                    (Đăng ký LoginAttempt, SchedulingState, StorageReservation)
│       │   ├── login_attempt.py                               (Model ghi nhận đăng nhập thất bại)
│       │   ├── scheduling_state.py                            (Model theo dõi điều phối bền vững user_scheduling_states)
│       │   ├── storage_reservation.py                         (Model đặt trước hạn ngạch storage_reservations)
│       │   └── user.py                                        (Trường storage_quota_mb, token_version)
│       ├── schemas/
│       │   └── auth.py                                        (UserPasswordChangeRequest)
│       └── services/
│           ├── audio_dsp_service.py                           (Dọn dẹp file tạm và commit/release reservation khi export)
│           ├── auth_service.py                                (Xác thực token_version, non-enumeration error message)
│           ├── durable_queue_service.py                       (4-tier anti-starvation scheduler, 25 jobs limit, reservation lifecycle)
│           ├── login_protection_service.py                    (Brute-force tracking theo ip & username)
│           ├── project_service.py                             (Bounded progressive batch submission & segment reconciliation)
│           └── user_quota_service.py                          (Two-phase reservation, commit, release, capacity calculation)
├── docs/
│   ├── CHANGELOG.md                                           (Ghi chép chi tiết thay đổi Phase 5A & Release Gate R1)
│   ├── decisions/adr/
│   │   └── ADR-0011-multi-user-rbac-and-resource-fairness.md  (Cập nhật kiến trúc Release Gate R1)
│   └── reports/
│       ├── phases/
│       │   ├── PHASE_05A_IMPLEMENTATION_REPORT.md             (Báo cáo hiện tại)
│       │   └── PHASE_05_KNOWN_LIMITATIONS.md                  (Ranh giới và giới hạn máy trạm)
│       ├── reviews/
│       │   ├── PHASE_05A_RELEASE_GATE_R1.md                   (Báo cáo thẩm định Release Gate R1)
│       │   └── PHASE_05A_SECURITY_REVIEW.md                   (Đánh giá an ninh độc lập Milestone 5A)
│       └── tests/
│           ├── PHASE_05A_CONCURRENCY_AND_SECURITY_EVIDENCE.md (Bằng chứng kiểm thử tương tranh và an ninh Gate R1)
│           └── PHASE_05A_TEST_EVIDENCE.md                     (Bằng chứng kiểm thử ban đầu Milestone 5A)
└── tests/
    └── integration/
        ├── test_migrations.py                                 (Cập nhật head revision assertion lên 20261009_0006)
        ├── test_phase5a_gate_r1_concurrency.py                (Bộ test tương tranh 7 kịch bản cho Gate R1)
        └── test_phase5a_rbac_and_fairness.py                  (Bộ test toàn diện 7 kịch bản cho Milestone 5A)
```

---

## 3. KẾT QUẢ KIỂM THỬ VÀ XÁC NHẬN CHẤT LƯỢNG

Toàn bộ hệ thống đã vượt qua 100% các bài kiểm thử hồi quy và kiểm thử tính năng mới mà không ghi nhận bất kỳ sự cố nào:

- **Bộ kiểm thử tương tranh Phase 5A Gate R1 (`tests/integration/test_phase5a_gate_r1_concurrency.py`)**:
  - `test_storage_reservation_concurrency_race`: **PASSED** (Đua tranh 2 tiến trình 80MB trên quota 100MB $\to$ 1 thành công, 1 nhận 413, 0 over-commit).
  - `test_storage_reservation_commit_and_release`: **PASSED** (Vòng đời 2 pha: reserve $\to$ commit $\to$ release khi fail).
  - `test_fair_share_anti_starvation_single_slot`: **PASSED** (User A nộp 25 job, User B nộp 1 job $\to$ điều phối xen kẽ A $\to$ B $\to$ A, không bị đói tác vụ).
  - `test_head_of_line_priority_precedence`: **PASSED** (Job độ ưu tiên cao được điều phối trước các job ưu tiên thấp).
  - `test_token_version_revocation_on_password_change`: **PASSED** (Đổi mật khẩu vô hiệu hóa token cũ ngay lập tức với 401 `TOKEN_REVOKED`).
  - `test_login_brute_force_per_username_and_ip`: **PASSED** (Khóa tài khoản bị dò sai mà không làm ảnh hưởng tài khoản khác trên cùng IP).
  - `test_long_form_progressive_batch_submission`: **PASSED** (Nộp kịch bản 30 segment vượt trần 25 $\to$ nạp lũy tiến tự động không phát sinh lỗi 429).

- **Bộ kiểm thử phân quyền & điều phối Phase 5A (`tests/integration/test_phase5a_rbac_and_fairness.py`)**:
  - **7/7 bài kiểm thử PASSED 100%**.

- **Bộ kiểm thử di trú cơ sở dữ liệu (`tests/integration/test_migrations.py`)**:
  - **4/4 bài kiểm thử PASSED 100%**.

- **Toàn bộ bộ kiểm thử hồi quy (Full Regression Test Suite)**:
  - **85 / 85 bài kiểm thử PASSED 100%** trong thời gian 4 phút 19 giây (259 giây).

- **Kiểm thử giao diện người dùng E2E trên Chrome (Playwright E2E Suite)**:
  - **4 / 4 bài kiểm thử E2E PASSED 100%** trong 54.96 giây.

- **Đóng gói giao diện sản xuất (Frontend Production Build)**:
  - `apps/web`: 1604 modules compiled sạch sẽ trong 13.77 giây, 0 lỗi TypeScript.

---

## 4. KẾT LUẬN & BƯỚC TIẾP THEO

Milestone 5A đã hoàn thành xuất sắc toàn bộ các mục tiêu đặt ra: củng cố an ninh xác thực, bảo vệ hạn ngạch lưu trữ nguyên tử, điều phối hàng đợi công bằng chống starvation, và hỗ trợ kịch bản dài tập lũy tiến. Hệ thống đạt trạng thái chấp thuận hoàn toàn (Acceptance PASS) trên môi trường máy trạm cục bộ.

**Ranh giới nghiêm ngặt:** Hệ thống hiện tại tiếp tục vận hành trên `127.0.0.1`. Giai đoạn 5B (LAN Deployment, Caddy Reverse Proxy, Self-signed TLS, Firewall) **KHÔNG ĐƯỢC PHÉP BẮT ĐẦU** cho đến khi có chỉ thị phê duyệt tiếp theo từ cấp thẩm quyền.
