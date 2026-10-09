# Documentation changelog

## 2026-10-09 — Phase 5B-1: Reverse Proxy Staging, Trusted Client Identity & Gateway Hardening (Acceptance PASS / Conditional Runtime)

- **Dàn dựng Cổng Reverse Proxy Loopback (Loopback Gateway Staging trên `127.0.0.1:9443`):**
  - Cấu hình Caddy Reverse Proxy hoàn chỉnh trong `infra/caddy/Caddyfile` với `tls internal` (Caddy Internal CA tự động phát hành chứng chỉ TLS ECDSA P-256).
  - Tích hợp tiêu đề bảo mật biên chuẩn OWASP: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, che giấu banner máy chủ (`-Server`).
  - Hỗ trợ truyền phát Server-Sent Events (SSE) thời gian thực không bộ đệm (`flush_interval -1` trên `/api/v1/jobs/stream`).
  - Chuyển tiếp an toàn mọi yêu cầu API và tệp tĩnh SPA về backend FastAPI tại `127.0.0.1:8765`.
- **Trích xuất IP Khách Tin Cậy & Chống Giả Mạo IP (RFC 7239 / OWASP Trusted Client IP Resolver):**
  - Triển khai `extract_client_ip` và `normalize_ip` trong `apps/server/src/core/network.py`:
    - Chỉ tin cậy các tiêu đề chuyển tiếp (`X-Forwarded-For`, `X-Real-IP`) khi socket peer kết nối trực tiếp là một proxy được tin cậy (`settings.TRUSTED_PROXIES = ["127.0.0.1", "::1"]`).
    - Phớt lờ 100% tiêu đề chuyển tiếp từ các kết nối trực tiếp không tin cậy, triệt tiêu hoàn toàn kỹ thuật vượt rate limit bằng IP spoofing.
    - Phân giải chuỗi proxy từ phải sang trái (right-to-left), loại bỏ cổng và kiểm tra hợp lệ qua `ipaddress.ip_address`.
  - Cập nhật endpoint `/api/v1/auth/login` để trích xuất IP qua resolver tin cậy, cô lập hoàn toàn ngân sách đăng nhập giữa các biên tập viên kết nối qua reverse proxy.
- **Khóa Độc Quyền Tiến Trình Runner Cấp OS (OS-Level Standalone Runner Process Lock):**
  - Triển khai lớp `RunnerProcessLock` trong `apps/server/src/runner.py` sử dụng khóa file độc quyền cấp nhân hệ điều hành (`msvcrt.locking(LK_NBLCK)` trên Windows và `fcntl.flock` trên Unix) tại `.runner.lock`.
  - Ngăn chặn tuyệt đối việc khởi chạy đè hai tiến trình Runner gây xung đột cổng engine worker hoặc tranh chấp slot tài nguyên.
- **Bảo Toàn Ranh Giới An Ninh Phase 4 & 5A:**
  - Tiếp tục từ chối tuyệt đối xác thực token qua URL query parameters (`QUERY_AUTH_PROHIBITED`, HTTP 400/401) trên mọi endpoint tải và stream âm thanh.
  - Bảo toàn 1 GPU slot duy nhất, chế độ SQLite WAL, và phân quyền RBAC.
- **Bộ Kiểm Thử Toàn Diện & Chứng Minh An Ninh:**
  - 12/12 ca kiểm thử chuyên sâu Milestone 5B-1 PASSED 100% (`tests/integration/test_phase5b1_trusted_proxy.py`).
  - 111/111 ca kiểm thử tích hợp (integration tests) PASSED 100%.
  - 9/9 ca kiểm thử unit & contract PASSED 100%.
  - 4/4 ca kiểm thử trình duyệt E2E Playwright PASSED 100%.
  - Frontend production build hoàn thành hoàn hảo (0 lỗi TypeScript).
  - Bản sao lưu cơ sở dữ liệu `studio_20261009_031341.db` (SHA256: `d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527`, 15 bảng toàn vẹn).
- **Trạng thái Caddy Runtime & Kế hoạch 5B-2:**
  - Ghi nhận trạng thái tệp thực thi Caddy chưa có sẵn trong PATH hệ thống; runtime trực tiếp trên cổng 9443 ở trạng thái CONDITIONAL.
  - Lập tài liệu vận hành chi tiết `infra/caddy/README.md` và kế hoạch chưa thực thi `docs/operations/PHASE_05B_LAN_ROLLOUT_AND_ROLLBACK.md` cho Milestone 5B-2.

## 2026-10-09 — Phase 5A Final Closure R2: Authentication Throttling, Quota Lease Safety & Autonomous Batch Processing (Acceptance PASS)

- **Hệ Thống Điều Tiết Xác Thực 3 Tầng Độc Lập (Priority P0 Multi-Tier Login Throttling):**
  - Mở rộng `LoginProtectionService` với 3 tầng phòng thủ độc lập:
    1. Cặp `(ip_address, username)` $\ge 5$ lần thất bại $\to$ Khóa cặp 15 phút.
    2. Tài khoản `username` trên mọi IP nguồn $\ge 10$ lần thất bại $\to$ Khóa tài khoản 15 phút (chống tấn công brute-force phân tán).
    3. IP nguồn trên mọi tài khoản $\ge 20$ lần thất bại $\to$ Khóa IP nguồn 15 phút (chống tấn công credential spraying).
  - Trích xuất IP an toàn từ socket TCP peer (`request.client.host`), loại bỏ triệt để nguy cơ IP spoofing qua `X-Forwarded-For`.
  - Phản hồi đồng nhất HTTP 401 `INVALID_CREDENTIALS` chống dò quét tài khoản (Enumeration Resistance).
- **Vòng Đời Hạn Ngạch Nguyên Tử & An Toàn Thuê (Atomic Quota Reservation Lifecycle & Lease Safety):**
  - Bổ sung `renew_job_reservation`: Tự động gia hạn TTL của reservation thêm 1800 giây trong mỗi nhịp heartbeat của worker.
  - Cải tiến `cleanup_expired_reservations`: Bảo vệ tuyệt đối các tác vụ đang `QUEUED`, `PREPARING`, `RUNNING` có lease hợp lệ khỏi việc thu hồi sớm.
  - Từ chối công nhân trễ hạn (stale worker) với HTTP 409 `RESERVATION_STALE_OR_RECLAIMED` khi reservation đã bị thu hồi hoặc hết hạn.
  - Bọc quy trình `AudioDspService.export_project` trong xử lý nguyên tử: Giải phóng reservation và xóa sạch tệp tạm (`unlink`) khi xuất bản lỗi.
- **Phân Tích Đánh Đổi Độ Ưu Tiên & Bỏ Đói (Priority Fairness & Starvation Trade-offs):**
  - Chứng minh bằng thực nghiệm: Round-Robin công bằng trong cùng cấp ưu tiên, Head-of-Line Priority Precedence giữa các cấp ưu tiên khác nhau.
  - Tài liệu hóa quyết định không áp dụng Priority Aging nhằm bảo vệ mục tiêu kinh doanh/nghiệp vụ cấp bách của phòng thu âm.
- **Xử Lý Kịch Bản Dài Tập Tự Trị (Autonomous Progressive Batch Processing):**
  - Tích hợp `reconcile_and_admit_pending_segments` vào vòng lặp nền của `DurableJobScheduler` với Admission Lock (`asyncio.Lock`) và Idempotency Key duy nhất (`seg-{segment_id}-{text_hash[:32]}`).
  - Kiểm chứng thành công kịch bản nộp 100 phân đoạn mà không cần polling từ trình duyệt (`GET /projects`), vượt qua an toàn sự cố khởi động lại API và Runner, sinh ra 100 audio artifact độc bản.
- **Sao Lưu Cơ Sở Dữ Liệu SQLite Qua CLI:**
  - Hoàn thành xác thực `python -m apps.server.src.backup create` và `verify` trên tệp `studio_20261009_021229.db` (417,792 bytes, SHA256: `d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527`, integrity `ok`, đủ 15 bảng).
- **Kiểm Thử Toàn Diện & Đóng Gói Sản Phẩm:**
  - 102/102 bài kiểm thử unit & integration PASSED 100% (275s).
  - 4/4 bài kiểm thử trình duyệt E2E Playwright PASSED 100%.
  - Frontend production build thành công (1604 modules, 0 lỗi TypeScript).

## 2026-10-09 — Phase 5A Release Gate R1: Fair-Share Correctness, Atomic Quotas & Multi-User Security (Acceptance PASS)

- **Điều Phối Công Bằng Đa Tầng & Chống Bỏ Đói (4-Tier Anti-Starvation Fair-Share Scheduling):**
  - Khắc phục triệt để nguy cơ starvation khi phần cứng chỉ có 1 GPU slot (`max_gpu_slots = 1`): Thay thế cơ chế đếm in-flight tức thời bằng bảng trạng thái bền vững `user_scheduling_states` ghi nhận `last_dispatched_at` theo từng loại tài nguyên.
  - Thuật toán 4 tầng trong `DurableQueueService.claim_next_job`: Tầng 1 (Head-of-Line Priority Precedence: `-c.priority`), Tầng 2 (In-flight burden), Tầng 3 (Persistent Anti-starvation round-robin: `last_dispatched_at ASC`), Tầng 4 (FIFO: `c.queued_at ASC`).
  - Đã xác thực thực tế: Người dùng A nộp 25 job, Người dùng B nộp 1 job $\to$ điều phối xen kẽ A1 $\to$ B1 $\to$ A2, hoàn toàn không bị kẹt.
- **Hạn Ngạch Lưu Trữ Nguyên Tử 2 Pha (Atomic Two-Phase Storage Quota Reservation):**
  - Khắc phục nguy cơ over-commit do đua tranh (race condition): Triển khai bảng `storage_reservations` và quy trình 2 pha trong `UserQuotaService` (`reserve_capacity` $\to$ `commit_reservation` / `release_reservation`).
  - Tích hợp vòng đời reservation tự động trên `submit_speech_job`, `complete_job`, `fail_job`, `cancel_job`, `upload_reference_audio`, và `export_project`.
  - Đã xác thực thực tế: 2 luồng đồng thời 80MB trên quota 100MB $\to$ đúng 1 luồng thành công, 1 luồng nhận HTTP 413, 0 bytes over-commit.
- **Bảo Vệ Đăng Nhập & Thu Hồi Phiên Tức Thì (Session Invalidation & Brute-Force Scoping):**
  - Bổ sung `users.token_version`. Đổi mật khẩu lập tức tăng `token_version`, vô hiệu hóa toàn bộ token cũ với HTTP 401 `TOKEN_REVOKED`.
  - Giới hạn khóa brute-force theo cặp `(ip_address, username)`: Dò quét sai 5 lần một tài khoản không làm ảnh hưởng tài khoản khác trên cùng IP (chống Collateral DoS).
- **Tương Thích Kịch Bản Dài Tập (Bounded Progressive Batch Submission):**
  - `ProjectService.render_batch` và `reconcile_project_segments` hỗ trợ nộp batch vượt ngưỡng 25 segment bằng cơ chế nạp lũy tiến tự động (tối đa 25 active jobs, các segment còn lại chuyển sang `"pending"` và được tự động đưa vào hàng đợi khi slot giải phóng), không phát sinh HTTP 429.
- **Di Trú Cơ Sở Dữ Liệu An Toàn & Chuẩn Hóa Sao Lưu SQLite:**
  - Áp dụng migration `alembic/versions/20261009_0006_phase5a_gate_r1_hardening.py` (`user_scheduling_states`, `storage_reservations`, `users.token_version`).
  - Chuẩn hóa quy trình sao lưu bằng SQLite Online Backup API CLI: Tệp sao lưu `D:\AIVoiceStudioData\backups\studio_20261009_011545.db` (405,504 bytes, SHA-256: `660e25e384fd2a083991d12c809b799e34a033a314101227eb123bcbdf88f280`, `PRAGMA integrity_check = ok`, đủ 15 bảng).
  - Đánh dấu bản sao lưu cũ bằng PowerShell `Copy-Item` là `UNVERIFIED` và hoàn thành kiểm thử phục hồi độc lập trên DB tạm thời.
- **Kiểm Thử Toàn Diện & Biên Dịch Giao Diện:**
  - 7/7 bài kiểm thử tương tranh và bảo mật Release Gate R1 PASSED.
  - 85/85 bài kiểm thử hồi quy toàn repository PASSED 100% (259s).
  - 4/4 bài kiểm thử trình duyệt Chrome E2E Playwright PASSED (54.96s).
  - Frontend production build hoàn thành hoàn hảo (0 lỗi TypeScript).

## 2026-10-09 — Phase 5A: Multi-User Core Hardening & Fair Resource Scheduling (Gate PASS)

- **Ma Trận Phân Quyền & Kiểm Soát Truy Cập Tiêu Cực (RBAC & Negative Authorization):**
  - Áp dụng triệt để dependency `require_editor` trên tất cả các route biến đổi dữ liệu (mutations) tại `projects.py`, `jobs.py`, và `assets.py`. Người dùng vai trò `viewer` bị từ chối với HTTP 403 `FORBIDDEN_INSUFFICIENT_PERMISSIONS`.
  - Giữ vững chốt chặn an toàn `FORBIDDEN_USER_CREATION` tại `POST /auth/users`, từ chối người dùng thông thường cố tình khởi tạo tài khoản.
- **Cách Ly Quyền Sở Hữu Voice Cloning (Strict Audio Reference Ownership):**
  - Loại bỏ hoàn toàn đặc quyền Admin âm thầm sử dụng mẫu giọng của người khác trong `durable_queue_service.py` (`asset_rec.user_id == current_user.id`), trả về HTTP 403 `FORBIDDEN_ASSET_ACCESS` khi vi phạm.
- **Kế Toán & Cưỡng Chế Hạn Ngạch Lưu Trữ Người Dùng (Non-destructive Storage Quotas):**
  - Bổ sung trường `users.storage_quota_mb` (mặc định 2048 MB = 2 GB).
  - Triển khai `UserQuotaService` hạch toán chính xác tổng dung lượng lưu trữ trên đĩa (`artifacts`, `master_exports`, `assets`).
  - Cưỡng chế HTTP 413 `USER_STORAGE_QUOTA_EXCEEDED` tại upload reference, submit speech job, và ghép nối master export. Đảm bảo dọn dẹp nguyên tử tệp tạm khi phát sinh lỗi.
- **Bộ Điều Phối Tài Nguyên Công Bằng (Fair-Share Scheduling & Priority Preemption):**
  - Cải tiến `DurableQueueService.claim_next_job`: Ưu tiên cấp phát slot phần cứng (1 GPU, 1 CPU) theo nguyên tắc **Least-Active-User-First** trong cùng một nhóm ưu tiên (`priority`).
  - Duy trì cơ chế ưu tiên vượt cấp (**Priority Preemption**): Job có độ ưu tiên cao hơn luôn được chọn trước.
  - Áp dụng giới hạn `MAX_OUTSTANDING_JOBS_PER_USER = 25`, từ chối với HTTP 429 `TOO_MANY_OUTSTANDING_JOBS` nếu người dùng vượt trần cho phép.
- **Bảo Vệ Đăng Nhập & Chống Dò Quét Tài Khoản (Brute-Force & Credential Hardening):**
  - Tạo bảng `login_attempts` và dịch vụ `LoginProtectionService` với cơ chế Sliding Window 15 phút. Khóa tài khoản/IP tạm thời sau 5 lần sai mật khẩu với HTTP 429 `TOO_MANY_LOGIN_ATTEMPTS` kèm header `Retry-After: 900`.
  - Bảo vệ chống user enumeration bằng thông điệp trung lập `"Incorrect username or password."`.
  - Triển khai endpoint đổi mật khẩu an toàn với xác thực mật khẩu hiện tại và độ dài tối thiểu $\ge 8$ ký tự.
- **Di Trú Cơ Sở Dữ Liệu An Toàn (Database Migration 20261009_0005):**
  - Tập lệnh `alembic/versions/20261009_0005_phase5a_rbac_and_quotas.py` tạo bảng `login_attempts` và thêm cột `storage_quota_mb`.
  - Cập nhật test migration và sao lưu an toàn cơ sở dữ liệu sản xuất tại `D:\AIVoiceStudioData\backups/`.
- **Bảo Đảm Chất Lượng & Kiểm Thử Toàn Diện:**
  - 7/7 bài kiểm thử tích hợp chuyên biệt cho Phase 5A PASSED.
  - 78/78 bài kiểm thử toàn bộ hệ thống PASSED 100% trong 186s.
  - Frontend TypeScript & Vite build thành công sạch sẽ (0 lỗi).

## 2026-10-09 — Phase 4 Security Hotfix R2: Remove JWT Query Authentication from Master Audio Downloads (Independent Security PASS)

- **CWE-598 Remediation (Removal of Query Parameter Authentication):**
  - Removed `get_current_user_flexible` completely from `apps/server/src/services/auth_service.py`.
  - Reverted authentication dependency on Master Audio download endpoint (`download_master_audio` in `apps/server/src/api/v1/projects.py`) and Artifact download endpoint (`get_artifact_audio_file` in `apps/server/src/api/v1/artifacts.py`) strictly to `current_user: User = Depends(get_current_user)`.
  - Added strict guardrail rejecting any request containing `token` in URL query parameters with HTTP 400 Bad Request (`QUERY_AUTH_PROHIBITED`), preventing credential leakage in access logs, proxy logs, and browser history.
  - Added security response headers: `Cache-Control: private, no-cache, no-store, must-revalidate` and `Pragma: no-cache`.
- **Frontend Secure Fetch & Blob URL Download Flow:**
  - Removed `getMasterExportDownloadUrl` from `apps/web/src/api/client.ts`.
  - Implemented `downloadMasterAudio(projectId, exportId, fallbackFilename)` utilizing `fetch()` with standard `Authorization: Bearer <token>` header, parsing `Content-Disposition`, constructing an in-memory `Blob` object, generating a short-lived Object URL (`URL.createObjectURL`), programmatically triggering download, and revoking the Object URL with `URL.revokeObjectURL`.
  - Converted download anchors (`<a>`) in `apps/web/src/components/MasterExportModal.tsx` to `<button>` elements calling `handleDownload`, ensuring no JWT appears in DOM attributes.
  - Successfully recompiled frontend production bundle (`apps/web/dist`) via `npm run build`.
- **Test Suite Updates & Security Regression:**
  - Updated `tests/integration/test_projects_api.py`: verified header Bearer downloads succeed with `no-store` cache header, verified query token requests are rejected with 400 `QUERY_AUTH_PROHIBITED`, verified cross-user 403 and unauthenticated 401.
  - Updated `tests/e2e/test_phase4_ui_export_download_ci.py`: verified Playwright browser download via buttons, verified 0 requests contained `token=` query parameter, verified 400 `QUERY_AUTH_PROHIBITED` on direct query access.
- **Independent Security Review Deliverable Published:**
  - `docs/reports/reviews/PHASE_04_SECURITY_HOTFIX_R2.md`.

## 2026-10-08 — Phase 4 Final UI Acceptance Gate: Browser Master Export & Download Verified (Independent PASS)

- **Root Cause Resolution for Browser Audio Download:**
  - Implemented `get_current_user_flexible` in `apps/server/src/services/auth_service.py` to support query parameter authentication (`?token=<jwt>`) exclusively for HTML download anchor tags where custom HTTP headers cannot be attached.
  - Implemented dual routing (`@router.get("/exports/{export_id}/download")` and `@router.get("/{project_id}/exports/{export_id}/download")`) in `apps/server/src/api/v1/projects.py` to reconcile client-server URL differences.
  - Added `Content-Disposition: attachment; filename="{filename}"` headers and verified cross-user access isolation (`403 Forbidden`).
  - Updated `apps/web/src/api/client.ts` (`getMasterExportDownloadUrl`) to append `?token=` parameter securely.
  - Recompiled production frontend bundle (`apps/web/dist`) with 0 errors.
- **Permanent Browser E2E Test Suite (Playwright Chrome):**
  - Implemented `tests/e2e/test_phase4_ui_export_download_ci.py`:
    - Full end-to-end journey from admin onboarding, project creation, text segmentation, UI state reconciliation, DSP master export (WAV & MP3), native browser download interception via `page.expect_download()`, and binary verification (WAV 48kHz, 16-bit PCM, duration > 2.0s).
    - Verified export history listing and re-download.
    - Verified security: HTTP 401 for unauthenticated requests, HTTP 403 for cross-user requests.
    - Executed in 7.50s (1/1 PASS).
  - Captured authentic screenshot: `docs/reports/screenshots/phase4_06_browser_download_verified.png` (136,630 bytes).
- **DSP Engineering Clarifications & Document Updates:**
  - Updated `docs/reports/PHASE_04_KNOWN_LIMITATIONS.md` to clearly distinguish the default `-16.0 LUFS` online podcast/streaming preset (AES TD1004 / Apple Podcasts) from the classical `-23.0 LUFS` European broadcast standard (EBU R128).
  - Documented True Peak limiter ceiling of `-1.5 dBTP` providing a 1.5 dB headroom safety margin to suppress intersample clipping, avoiding claims that clipping is mathematically impossible under lossy compression.
- **Independent Governance Deliverable Published:**
  - `docs/reports/reviews/PHASE_04_FINAL_UI_ACCEPTANCE.md`.

## 2026-10-08 — Phase 4 Acceptance Gate Remediation & Official Release Pass (Gate PASS)

- **Audit & Asynchronous Data Integrity Remediation:**
  - Resolved stale job overwrite vulnerability in `ProjectService.reconcile_project_segments` via deterministic `text_hash` comparison against in-flight job hashes.
  - Safeguarded non-destructive revision preservation in `SegmentRevisionRecord` when segments are edited mid-render.
  - Fixed relationship lazy loading with `lazy="selectin"` on `ScriptSegmentRecord.active_artifact` and `last_job`, eliminating `MissingGreenlet` exceptions in async SQLAlchemy operations.
  - Upgraded `get_project` API endpoint to automatically trigger reconciliation, providing live, up-to-date state to web clients.
- **Audio DSP & FFmpeg Mastering Hardening:**
  - Configured `STUDIO_FFMPEG_PATH` supporting host FFmpeg v7.1.1 essentials (GPLv3).
  - Implemented Two-Pass EBU R128 loudness normalization and True Peak limiting ($\le -1.0\text{ dBTP}$).
  - Fixed MP3 sample rate preservation with explicit `-ar <sample_rate>` flag.
  - Hardened Concat Demuxer against command/path injection via strict quotation escaping and ownership validation.
  - Implemented authentic technical measurements (`measure_audio_metrics`) capturing SHA-256, duration, sample rate, bit depth, Integrated LUFS, and True Peak dBTP.
- **Frontend Studio UI Upgrades:**
  - Added 2-second auto-polling in `SpeechStudioView.tsx` and `DialogueStudioView.tsx` during background rendering.
  - Rebuilt production bundle (`apps/web/dist`) cleanly with 0 errors.
- **Authentic Audio Production Deliverables (4 Workflows):**
  - Generated 4 real master audio files in `D:\AIVoiceStudioData\acceptance_audio_phase4\`:
    1. `workflow_a_vietnamese_master.wav`: VieNeu CPU 48kHz, 23.10s, -16.11 LUFS, -1.5 dBTP, SHA256: `beb17a4125c3...`
    2. `workflow_b_chinese_master.mp3`: Qwen3 GPU 48kHz resampled 192kbps, 27.72s, -16.27 LUFS, -1.5 dBTP, SHA256: `2665833fffa7...`
    3. `workflow_c_mixed_dialogue_master.wav`: Lan & Mei mixed dialogue, 21.63s, -16.19 LUFS, -1.5 dBTP, SHA256: `bc8778f9c8a3...`
    4. `workflow_c_mixed_dialogue_master.mp3`: Lan & Mei mixed dialogue 192kbps, 21.67s, -16.19 LUFS, -1.5 dBTP, SHA256: `612857aeb141...`
    5. `metrics_summary.json`: Detailed measurement metrics report.
- **Full Two-Tier Regression Suite (100% PASS):**
  - 78/78 tests passed in 222.48s (0 failed, 0 skipped), including all Unit, Contract, Security, Integration, Data Integrity, and Chrome Browser E2E tests.
- **Database Backup & Restore Verification:**
  - Created verified SQLite online backup: `studio_20261008_154951.db` (344,064 bytes, all 12 tables verified).
  - Validated independent restoration without downtime or data corruption.
- **Governance Deliverables Published:**
  - `docs/reports/reviews/PHASE_04_ACCEPTANCE_REVIEW.md`
  - `docs/reports/tests/PHASE_04_END_TO_END_EVIDENCE.md`
  - `docs/reports/benchmarks/PHASE_04_MASTER_AUDIO_VALIDATION.md`
  - `docs/reports/phases/PHASE_04_REMEDIATION_CHANGELOG.md`

## 2026-10-08 — Phase 4 Professional Studio UX, Long-Form TTS, Dialogue Workspace & Audio Mastering Completed

- **Milestone 4A (Project Workspace & Optimistic Concurrency Control):**
  - Applied Alembic migration `20261008_0004_phase4_studio.py` introducing 5 new tables: `projects`, `characters`, `script_segments`, `segment_revisions`, and `project_exports`.
  - Implemented optimistic locking with strict HTTP `409 Conflict` checks on mismatched `expected_version` / `expected_project_version`.
  - Implemented multi-user data isolation with HTTP `403 Forbidden` across foreign project boundaries.
- **Milestone 4B (Long-form Speech Studio & Intelligent Segmentation):**
  - Created `TextSegmenter` with language-aware linguistic boundaries for Vietnamese (< 220 chars, protecting abbreviations TP., TS., GS.) and Mandarin Chinese (< 120 chars, honoring `。！？；…`).
  - Implemented partial invalidation: segment text modifications automatically flip status to `stale` (Needs Regeneration) while preserving `active_artifact_id`.
  - Implemented non-destructive audio revisions in `SegmentRevisionRecord` for auditioning prior renders.
- **Milestone 4C (Multi-Character Dialogue Studio):**
  - Created Character Persona panel with customizable avatar color badges, fixed voice assignments, and multi-engine routing (VieNeu 48kHz CPU vs Qwen3 24kHz GPU).
  - Built dialogue timeline stream with per-line speaker dropdown, editable text, and configurable turn-taking pauses (200ms–1500ms).
- **Milestone 4D (Audio DSP, Mastering & Export):**
  - Created `AudioDspService` wrapping local FFmpeg 7.1.1 essentials securely via subprocess argument lists and temporary concat demuxer manifests (bypassing Windows 8191-character CLI limits).
  - Implemented sample rate normalization via high-quality SOXR resampler (`aresample=resampler=soxr`) for mixed 48kHz + 24kHz inputs.
  - Implemented international broadcast loudness mastering via two-pass EBU R128 (`loudnorm=I=-16.0` or `-23.0 LUFS`).
  - Supported master export to WAV (PCM 16-bit Lossless) and MP3 (320 kbps High Quality) with SHA-256 integrity validation.
- **Frontend Professional Workstation UI:**
  - Implemented `ProjectsView.tsx`, `SpeechStudioView.tsx`, `DialogueStudioView.tsx`, and `MasterExportModal.tsx`.
  - Upgraded `Header.tsx` and `App.tsx` navigation. Cleanly compiled production bundle (`apps/web/dist`) with 0 errors.
- **Full Two-Tier Regression & Playwright Verification (100% PASS):**
  - 67/67 Pytest unit & integration tests passed in 2m22s (0 failed).
  - 1/1 Playwright Real Chrome Browser E2E test passed in 6.5s.
  - Captured 5 authentic 1366x900 screenshots in `docs/reports/screenshots/phase4_*.png`.
- **Published Deliverables:** `PHASE_04_PROFESSIONAL_STUDIO.md`, `PHASE_04_IMPLEMENTATION_REPORT.md`, `PHASE_04_TEST_EVIDENCE.md`, `PHASE_04_KNOWN_LIMITATIONS.md`, and `PHASE_04_AUDIO_EXPORT_VALIDATION.md`.

- **Remediated Secure Voice Cloning Pipeline:** Eliminated server filesystem path injection vectors (`ref_audio`). Implemented `ReferenceAssetRecord` in `apps/server/src/models/asset.py` with Alembic migration `20261008_0003_reference_assets.py`. Created `AssetService` validating RIFF/WAVE headers (0.5s–30s duration, <=15MB), enforcing UUID server paths, cross-user authorization isolation (`403 Forbidden`), and requiring explicit user legal consent (`voice_use_consent`).
- **Engine Parameter Contract Hardening:** `DurableQueueService` strictly validates requested engine capabilities (`VOICE_CLONING_NOT_SUPPORTED`), manifests `parameters_schema` keys (`UNSUPPORTED_PARAMETER`), range limits for `speed` and enum for Qwen3 `speaker` (`INVALID_PARAMETER_VALUE`), and voice catalog membership (`UNSUPPORTED_VOICE`).
- **Frontend Voice Cloning UI Overhaul:** Upgraded `StudioView.tsx` with dedicated WAV file upload, library asset dropdown, and legal consent checkbox. Rebuilt production bundle (`apps/web/dist`) cleanly with 0 errors.
- **Two-Tier Regression Test Suite (100% PASS):** Executed full regression suite:
  - **Tier 1 (Fast CI Suite):** 42/42 tests passed in 52.24s (0 failed, 0 skipped).
  - **Tier 2 (Hardware Integration Suite):** 15/15 tests passed in 131.43s (0 failed, 0 skipped).
  - **Total:** 57/57 tests passing (100%).
- **Authentic Acceptance Audio Package Generated:** Produced 4 real WAV files in `D:\AIVoiceStudioData\acceptance_audio_phase3\` outside Git:
  1. `vi_male_haidang.wav`: VieNeu preset "Hải Đăng", 9.36s, 48kHz, RTF 1.39, SHA256: `b613c8f089dfbd06...`
  2. `vi_female_maianh.wav`: VieNeu preset "Mai Anh", 10.16s, 48kHz, RTF 0.62, SHA256: `4856259e21e7633d...`
  3. `vi_cloned_sample.wav`: VieNeu zero-shot clone from verified reference WAV, 9.20s, 48kHz, RTF 0.92, SHA256: `e76240d67c3e7845...`
  4. `zh_female_vivian.wav`: Qwen3 preset "Vivian" on CUDA GPU, 12.40s, 24kHz, RTF 2.48, SHA256: `bb55e28b67f71e69...`
- **Hardware Telemetry Verified:**
  - PyTorch CUDA allocated: 2,065.0 MB; Peak board VRAM (nvidia-smi): 3,523.0 MB / 6,144.0 MB (57.3% usage); 2,747.0 MB cleanly reclaimed post-shutdown.
  - VieNeu CPU worker RAM RSS: 2,444.0 MB, fully released upon worker termination.
- **Scientific Honesty & Governance Compliance:** Documented Qwen3 RTF > 1.0 (2.48) as slower-than-real-time; classified voice cloning perceptual quality as **UNVERIFIED HUMAN-PERCEIVED SIMILARITY**; retained external CUDA OOM risk boundaries.
- **Published Deliverables:** `PHASE_03_ACCEPTANCE_REVIEW.md`, `PHASE_03_FULL_REGRESSION.md`, and `PHASE_03_AUDIO_ACCEPTANCE.md`.

## 2026-10-08 — Phase 3 Production AI Engine Adapters & End-to-End Inference Integration Completed

- **Mandatory Pre-Flight Gate Verification:** Passed all 6 pre-flight gate tests (`test_phase3_preflight.py` in 4.03s), verifying dual-scheduler conflict prevention, standalone runner execution, crash recovery with at-least-once semantics, cross-process GPU slot atomicity, and SSE replay across server restarts.
- **Production Engine A (VieNeu-TTS v3 Turbo):** Implemented production adapter in `engines/vieneu/` running isolated in Python 3.12 (`vieneu_env`) on CPU via ONNX Runtime FP32. Supports 22 preset Vietnamese voices, zero-shot voice cloning with reference audio embedding extraction, and 48kHz WAV audio export. Verified with contract tests (`test_vieneu_engine.py` passed in 23.13s).
- **Production Engine B (Qwen3-TTS 0.6B CustomVoice):** Implemented production adapter in `engines/qwen3/` running isolated in Python 3.12 (`qwen3_env`) on GPU NVIDIA GeForce RTX 3050 (6GB VRAM, `bfloat16`). Supports 9 built-in speakers for Mandarin Chinese, 24kHz WAV export, CUDA OOM recovery, and strictly rejects voice cloning. Verified with contract tests (`test_qwen3_engine.py` passed in 78.74s).
- **Core Pipeline Upgrades:** Added `parameters: Dict[str, Any]` to `TTSJobSubmitRequest`, forwarded parameters through `DurableJobScheduler`, upgraded `ProcessSupervisor` to resolve absolute `virtualenv_path`, and increased `EngineWorkerClient` timeout to 180s.
- **Frontend UI Phase 3 Upgrade:** Upgraded `StudioView.tsx` with dynamic AI Engine dropdown, target device indicators (CPU vs GPU CUDA), preset voices, zero-shot voice cloning mode with reference WAV input and denoise toggle, and real-time audio playback for 24kHz and 48kHz WAV files. Production bundle cleanly rebuilt with 0 errors.
- **End-to-End Integration Tests:** Implemented `test_phase3_integration.py` passing 100% (4/4 passed in 67.44s) covering VieNeu 48kHz pipeline, VieNeu voice cloning, Qwen3 24kHz pipeline on RTX 3050, and CPU/GPU concurrency and slot isolation.
- **Real Chrome Browser E2E Playwright:** Implemented `test_phase3_browser_e2e.py` passing 100% in 20.17s; generated 6 authentic screenshots in `docs/reports/screenshots/` (0 console errors, 0 network failures).
- **Hardware Telemetry & Runtime Benchmarking:** Executed `scripts/benchmark_phase3_metrics.py`. Measured VieNeu warm RTF = 0.66 (faster than real-time), Qwen3 warm RTF = 1.63 (slower than real-time), Qwen3 allocated VRAM = 2,065 MB.
- **Published Deliverables:** `PHASE_03_ENGINE_INTEGRATION.md`, `PHASE_03_RUNTIME_METRICS.md`, `PHASE_03_IMPLEMENTATION_REPORT.md`, `PHASE_03_TEST_EVIDENCE.md`, and `PHASE_03_KNOWN_LIMITATIONS.md`.

## 2026-10-08 — Phase 2 Release Gate R1 Remediations Verified (Gate PASS)

- **P0 Security Remediated:** Eliminated JWT token query string parameter in SSE endpoint (`CWE-598`). Replaced browser `EventSource` with custom native `fetch()` streaming reader using `Authorization: Bearer` and `Last-Event-ID` HTTP headers in `apps/web/src/api/client.ts`. Backend `apps/server/src/api/v1/jobs.py` strictly rejects `?token=...` with HTTP `400 Bad Request` (`QUERY_AUTH_PROHIBITED`).
- **Decoupled Standalone Runner Process:** Added `apps/server/src/runner.py` allowing execution of `DurableJobScheduler` and inference worker supervision in an independent OS process separate from FastAPI. Added configuration setting `EMBEDDED_SCHEDULER` in `apps/server/src/config.py`. Proposed [ADR-0009](decisions/adr/ADR-0009-runner-process-and-online-backup.md).
- **Database-Backed Multi-Process Hardware Slot Enforcement:** `ResourceManager` enforces strict global hardware limits (max 1 GPU, max 1 CPU) across processes by querying active SQLite unexpired leases with self-counting prevention (`exclude_job_id`).
- **Safe SQLite Online Backup API & CLI Tool:** Created `BackupService` (`apps/server/src/services/backup_service.py`) and CLI `apps/server/src/backup.py` using `sqlite3.Connection.backup()` step-by-step (`pages=100`) for non-blocking live WAL backups. Verified `PRAGMA integrity_check` and safe restore. Audited existing database backups in `D:\AIVoiceStudioData` (`studio.db.phase1.bak` verified valid).
- **Process Failure Resilience Test Suite:** Implemented `tests/integration/test_process_resilience.py` validating 6 core failure scenarios (A through F): subprocess kill & recovery, fencing token stale worker rejection, race cancellation vs completion with zero orphan artifacts, multi-runner GPU slot limits, SSE stream reconnection & replay, and online backup during active WAL writes.
- **Automated Verification:** 34/34 tests passing (100%) in 22.62s; frontend production build cleanly regenerated (0 errors).
- **Published Deliverables:** `PHASE_02_RELEASE_GATE_REVIEW.md`, `PHASE_02_RELEASE_GATE_EVIDENCE.md`, and `PHASE_02_REMEDIATION_CHANGELOG.md`.

## 2026-10-08 — Phase 2 Durable Job Orchestration & Production Resilience Completed

- Backed up Phase 1 database: `D:\AIVoiceStudioData\studio.db.phase1.bak` and `D:\AIVoiceStudioData\backups\studio.db.phase1.bak`.
- Applied Alembic migration `20261008_0002_durable_jobs.py`: added priority, resource_type, attempt_count, max_retries, fencing token, locked_by, and created durable `job_events` table.
- Implemented `JobStateMachine` (`apps/server/src/services/job_state_machine.py`) with 6 explicit states (`queued`, `preparing`, `running`, `completed`, `failed`, `cancelled`) and `IllegalStateTransitionError`.
- Implemented `DurableQueueService` (`apps/server/src/services/durable_queue_service.py`): atomic claiming, fencing tokens (`current_attempt_id`), lease expiration reclaiming, exponential backoff retries, short transactions without SQLite locking during worker synthesis, and idempotency collision checks (`409 Conflict`).
- Implemented `ResourceManager` (`apps/server/src/services/resource_manager.py`): defensive slot limits (`max_gpu_slots = 1`, `max_cpu_slots = 1`, `max_global_slots = 2`) with waiting reasons.
- Implemented `DurableJobScheduler` daemon (`apps/server/src/supervisor/scheduler.py`) running in FastAPI lifespan, with startup crash recovery, background lease heartbeats, and graceful shutdown.
- Implemented Server-Sent Events (SSE) streaming (`GET /api/v1/jobs/{id}/events`) with query param token auth for EventSource, durable `job_events` persistence, and `Last-Event-ID` event replay.
- Updated Frontend UI (`StudioView.tsx`, `JobHistoryTable.tsx`, `client.ts`): cancel job button, manual retry button, attempt indicators, waiting reason badges, SSE real-time streaming with polling fallback, and reload persistence.
- Rebuilt frontend production bundle (`npm run build`).
- Automated testing expanded to 28 tests (100% passed in 18.30s), completely covering the 15 Phase 2 testing matrix categories and capturing 6 real Chrome browser Playwright screenshots.
- Published deliverables: `PHASE_02_DURABLE_QUEUE.md`, `PHASE_02_IMPLEMENTATION_REPORT.md`, `PHASE_02_TEST_EVIDENCE.md`, and `PHASE_02_KNOWN_LIMITATIONS.md`.
- Corrected Phase 1B documentation conclusions regarding total board VRAM, CUDA OOM risk boundaries, slower-than-real-time RTF, unverified concurrency, and voice cloning similarity status.

## 2026-10-08 — Phase 1B Engine Feasibility & Hardware Benchmark Completed

- Conducted pre-flight hardware and license verification for Intel Core i5-12400F and NVIDIA GeForce RTX 3050 (6GB VRAM) on Windows 11.
- Created isolated environments and model storage outside application repository (`D:\AIVoiceStudioData\benchmarks\`).
- Benchmarked VieNeu-TTS v3 Turbo on CPU (ONNX Runtime, torch-free): achieved RTF 0.55-0.75, 48kHz audio quality, 2.4GB peak RAM, zero memory leak across 5 repeated runs. Verdict: PASS.
- Benchmarked Qwen3-TTS 0.6B CustomVoice on GPU (PyTorch CUDA, bfloat16): peak VRAM only 2.77GB (well within 6GB limit), 24kHz audio, 9 preset speakers, error recovery verified in 4.4s. Verdict: PASS.
- Published benchmark deliverables: `PHASE_1B_ENVIRONMENT.md`, `VIENEU_BENCHMARK.md`, `QWEN3_BENCHMARK.md`, `PHASE_1B_COMPARISON.md`, and `PHASE_1B_FEASIBILITY_REPORT.md`.

## 2026-10-08 — Phase 1 Verification & Remediation Complete (Gate PH1 Ready)

- Revoked and redacted exposed bootstrap credential; implemented 15-minute TTL and atomic OS-level file rename (`os.replace`) preventing concurrent onboarding race conditions.
- Added multi-user RBAC service (`POST /api/v1/auth/users`) with role-based access control and strict artifact ownership cross-authorization isolation (403 Forbidden).
- Integrated Alembic database migration tooling (`alembic.ini`, `alembic/env.py`, initial revision `20261008_0001`) with automatic SQLite WAL and foreign key enforcement.
- Hardened Process Supervisor with native Windows Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) preventing orphan worker processes.
- Added explicit contract disclaimer banner to Web UI and rebuilt frontend production bundle.
- Executed real Google Chrome E2E test via Playwright across 12 user journey steps; recorded 5 authentic screenshots in `docs/reports/screenshots/` with 0 console errors and 0 network failures.
- Expanded automated test suite from 6 to 14 tests, achieving 100% pass rate (14/14 passed in 9.61s).
- Published verification reports: `PHASE_01_REVIEW_REPORT.md`, `PHASE_01_SECURITY_VERIFICATION.md`, `PHASE_01_E2E_TEST_RESULTS.md`, and `PHASE_01_REMEDIATION_CHANGELOG.md`.

## 2026-10-08 — Phase 1 Foundation & First Vertical Slice Completed

- Implemented Engine Adapter SDK v1 (`packages/engine_sdk`) with Pydantic v2 schemas and authenticated loopback HTTP client.
- Implemented Contract Mock Engine (`engines/mock`) generating pristine 16-bit PCM WAV audio with RFC 9457 error support.
- Built Headless Application Core (`apps/server`) with FastAPI, SQLite WAL persistence, Argon2id password hashing, JWT sessions, and one-time local bootstrap onboarding.
- Built Process Supervisor (`apps/server/src/supervisor`) with worker subprocess management, port allocation, and crash recovery.
- Built modern Web UI (`apps/web`) with React 19, TypeScript, Vite, and Tailwind CSS.
- Automated testing: 6/6 contract and integration tests passed (100%).
- Published reports: `PHASE_01_IMPLEMENTATION_REPORT.md`, `PHASE_01_TEST_EVIDENCE.md`, `PHASE_01_KNOWN_LIMITATIONS.md`, and `LOCAL_DEVELOPMENT.md`.

## 2026-10-08 — R1.1 Documentation Baseline Accepted (Gate DOC Passed)

- Product Owner formally accepted the Architecture R1.1 documentation pack as the official architectural baseline.
- Updated all 8 ADRs (ADR-0001 through ADR-0008) status to `accepted` under Product Owner authority.
- Recorded explicit condition: Hardware, GPU memory, inference latency, model audio quality, and Windows compatibility assumptions remain UNVERIFIED pending Phase 1B benchmarks.
- Published review report: `docs/reports/reviews/2026-10-08-documentation-acceptance.md`.
- Phase 1 implementation remains pending separate authorization (Gate PH1).

## 2026-10-08 — R1.1 (Proposed)

- Imported 9 Gemini R1 documents and kept exact originals in `archive/r1-original/`.
- Created long-term docs hierarchy, governance, versioned ADR register, phase plan, reports, ideas/research/specs/operations and templates.
- Reconciled canonical TTS API path (`/api/v1/jobs/speech`), safer SQLite claim/recovery semantics and stale worker fencing design.
- Hardened first-run bootstrap design; clarified plugin integrity is not signature/authenticity.
- Updated MCP design reference to 2026-07-28; qualified FFmpeg distribution obligations.
- Unified Phase 1 minimal mocked end-to-end acceptance and separated Phase 1B permissions.
- Marked model GPU figures as unverified pending benchmarks.

**Note:** This changelog records documentation edits only, not code or tests executed on the PC.
