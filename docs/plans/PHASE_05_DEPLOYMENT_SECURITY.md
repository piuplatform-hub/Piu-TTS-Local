---
id: PLAN-20261009-PHASE-05
title: Phase 5 Master Plan - Local Deployment, Multi-User Access & Operational Security
status: proposed
owner: Product Owner
created: 2026-10-09
updated: 2026-10-09
related: [ADR-0001, ADR-0003, ADR-0004, ADR-0006, ADR-0009, ADR-0010, ADR-0011, ADR-0012]
---

# AI VOICE STUDIO — KẾ HOẠCH TỔNG THỂ PHASE 5
## LOCAL WORKSTATION DEPLOYMENT, MULTI-USER ACCESS & OPERATIONAL SECURITY
### VẬN HÀNH MÁY TRẠM CỤC BỘ, TRUY CẬP ĐA NGƯỜI DÙNG & AN TOÀN VẬN HÀNH

- **Mã kế hoạch:** `PLAN-20261009-PHASE-05`
- **Vai trò thực hiện:** Principal Software Architect, Windows Deployment Engineer, Application Security Lead & Reliability Engineer
- **Ngày lập:** 2026-10-09
- **Trạng thái:** **PROPOSED (ĐỀ XUẤT — CHỜ PRODUCT OWNER PHÊ DUYỆT)**
- **Baseline kiến trúc:** Architecture R1.1 (Cam kết mốc Git Phase 4: `24b3102`)
- **Phạm vi được ủy quyền hiện tại:** **CHỈ LẬP KẾ HOẠCH & PREFLIGHT AUDIT** (Nghiêm cấm tự ý code, mở firewall, mở port LAN, hay cài đặt Windows services trước khi được phê duyệt).

---

## 1. BỐI CẢNH & MỤC TIÊU SẢN PHẨM (CONTEXT & OBJECTIVES)

Sau khi hoàn thành xuất sắc Phase 4 (Phòng thu âm chuyên nghiệp, xuất bản Master DSP EBU R128 và tải file an toàn 100% qua Fetch/Blob URL), hệ thống AI Voice Studio hiện đã là một ứng dụng sản xuất âm thanh hoàn chỉnh chạy trên máy trạm Windows 11 cá nhân (`127.0.0.1`).

Tuy nhiên, trong môi trường sản xuất nội dung thực tế (phòng thu âm nhỏ, nhóm biên tập sách nói, đài truyền thanh nội bộ), nhu cầu thực tế đòi hỏi:
1. **Nhiều biên tập viên (Multi-user)** cùng truy cập vào ứng dụng từ các máy tính làm việc khác nhau trong cùng mạng nội bộ (mạng LAN văn phòng/phòng thu).
2. **Dữ liệu và mô hình AI tập trung** trên một máy trạm duy nhất sở hữu GPU NVIDIA GeForce RTX 3050 (6GB VRAM) và CPU Intel Core i5-12400F (16GB RAM).
3. **An toàn bảo mật vận hành**: Mở mạng LAN nhưng **tuyệt đối không phơi bày ra Internet**, không lộ token, có chứng thực HTTPS/TLS bắt buộc, kiểm soát quyền hạn (RBAC), chống tấn công dò quét mật khẩu và chống cạn kiệt tài nguyên.
4. **Chia sẻ tài nguyên công bằng (Job Fairness)**: Ngăn chặn tình trạng một người dùng submit hàng trăm phân đoạn khiến toàn bộ người dùng khác bị tắc nghẽn hoàn toàn.
5. **Độ tin cậy vận hành (Operational Reliability)**: Khởi động tự động cùng Windows, phục hồi sự cố mất điện (Power-loss recovery), và quy trình sao lưu/khôi phục toàn vẹn dữ liệu (Full application-data backup & restore).

---

## 2. PHÂN TÁCH HIỆN TRẠNG: ĐÃ CÓ VS CẦN PHÁT TRIỂN MỚI

| Thành phần | Đã có từ Phase 0–4 (Hiện trạng) | Cần phát triển mới trong Phase 5 |
| :--- | :--- | :--- |
| **Kiến trúc mạng & Cổng** | Lắng nghe cục bộ `127.0.0.1:8765`, CORS hardcoded localhost. | Reverse Proxy (Caddy/Nginx) đầu mạng LAN với HTTPS/TLS; cấu hình CORS & Allowed Hosts linh hoạt. |
| **Quản lý tiến trình** | Khởi chạy thủ công từ terminal `python -m apps.server.src.main`. | Windows Service / Task Scheduler Watchdog tự động khởi động cùng Windows và phục hồi sau sự cố. |
| **Xác thực & Người dùng** | Bảng `users` có cột `role` (admin/editor/viewer); endpoint `/auth/bootstrap`, `/auth/login`, `/auth/users`. | RBAC phân quyền chặt chẽ trên mọi API; đổi mật khẩu cá nhân; Rate Limiter chống brute-force đăng nhập. |
| **Điều phối hàng đợi** | `DurableJobScheduler` sắp xếp FIFO theo độ ưu tiên `priority DESC, queued_at ASC`. | **Fair-Share Scheduler**: Điều phối công bằng theo vòng tròn người dùng (Per-User Round-Robin) chống chiếm dụng GPU. |
| **Quản lý tài nguyên** | `ResourceManager` khóa cứng tối đa 1 GPU slot, 1 CPU slot. | Giữ nguyên quy tắc 1 GPU slot (tránh CUDA OOM trên RTX 3050 6GB) nhưng bổ sung hạn mức in-flight per-user. |
| **Hạn mức lưu trữ** | Không giới hạn, ghi tự do vào `D:\AIVoiceStudioData`. | **User Storage Quotas**: Quản lý hạn mức đĩa (GB / Số dự án) cho từng người dùng, cảnh báo và dọn dẹp rác. |
| **Bảo vệ truyền file lớn** | Tải file qua Fetch + Blob URL; endpoint từ chối `?token=` (CWE-598). | HTTP Range request tối ưu cho master audio; Streaming chunked transfer; Rate limit tải file hàng loạt. |
| **Giám sát & Nhật ký** | Logging console chuẩn Python logging. | Structured Security Audit Logs (JSON); Endpoints kiểm tra sức khỏe `/health` và số liệu `/metrics`. |
| **Sao lưu & Khôi phục** | Script `backup.py` sao lưu online cho `studio.db` (Alembic rev 4). | **Full Backup Suite**: Tự động đóng gói cơ sở dữ liệu và thư mục artifacts/assets; quy trình khôi phục thảm họa 1-lệnh. |

---

## 3. THIẾT KẾ KIẾN TRÚC MÁY TRẠM ĐƠN LẺ CHO NHIỀU NGƯỜI DÙNG

```
[ Mạng Cục Bộ LAN Phòng Thu (192.168.1.0/24) ]
   │
   ├── [ Client Máy Biên Tập 1: Trình duyệt Chrome/Edge ] ──(HTTPS:443)──┐
   ├── [ Client Máy Biên Tập 2: Trình duyệt Chrome/Edge ] ──(HTTPS:443)──┤
   └── [ Client Máy Quản Trị  : Trình duyệt Chrome/Edge ] ──(HTTPS:443)──┤
                                                                         │
═════════════════════════════════════════════════════════════════════════╪═══════════════════════
 [ MÁY TRẠM VẬN HÀNH WINDOWS 11 (Intel i5-12400F | 16GB RAM | RTX 3050 6GB VRAM) ]
                                                                         │
   ┌─────────────────────────────────────────────────────────────────────┘
   │
   ▼
[ 1. CỔNG AN NINH ĐẦU BIÊN: LOCAL REVERSE PROXY (CADDY / NGINX) ]
   ├── Lắng nghe IP LAN (ví dụ: 192.168.1.100:443)
   ├── Quản lý chứng chỉ TLS nội bộ (Internal CA / mkcert tự động)
   ├── Rate Limiter đầu biên (Chặn DoS, Brute-force IP)
   ├── Phục vụ trực tiếp tệp giao diện Web tĩnh (apps/web/dist)
   └── Proxy ngược cục bộ (Loopback Proxy) ──► http://127.0.0.1:8765
                                                    │
   ┌────────────────────────────────────────────────┘
   ▼
[ 2. FASTAPI BACKEND API GATEWAY (127.0.0.1:8765) ]
   ├── Authentication & RBAC Middleware (Header: Bearer JWT)
   ├── Rate Limiting nghiệp vụ (Per-user request limits)
   ├── REST API Endpoints (/projects, /segments, /export, /artifacts)
   └── SSE Event Broadcaster (/jobs/{id}/events via Fetch ReadableStream)
         │
         ├── Đọc/Ghi dữ liệu bền vững
         ▼
[ 3. PERSISTENT STORAGE LAYER (D:\AIVoiceStudioData) ]
   ├── SQLite WAL Database (studio.db) ── Hàng đợi nhiệm vụ & Trạng thái dự án
   ├── Audio Artifacts Store (/artifacts) ── Tệp WAV phân đoạn
   └── Master Exports Store (/artifacts/exports) ── Tệp Master WAV/MP3 hoàn chỉnh
         ▲
         │ Polling & Claiming nhiệm vụ qua DB Lease
[ 4. STANDALONE DURABLE RUNNER PROCESS (python -m apps.server.src.runner) ]
   ├── Fair-Share Scheduler (Per-User Round-Robin)
   ├── ResourceManager (Khóa cứng: Max 1 GPU Slot | Max 1 CPU Slot)
   └── Supervisor (Windows Job Objects cách ly tiến trình Worker)
         │
         ├── Worker 1 (CPU): VieNeu-TTS Worker (PID riêng, cách ly bộ nhớ)
         └── Worker 2 (GPU): Qwen3-TTS Worker (PID riêng, giới hạn 3.8GB VRAM)
```

---

## 4. CHIẾN LƯỢC TRIỂN KHAI PHÂN KỲ (4 MILESTONES CỦA PHASE 5)

### Milestone 5A: Củng Cố An Ninh API, Phân Quyền RBAC & Lập Lịch Công Bằng (Core Backend Hardening)
1. **Phân quyền RBAC (Role-Based Access Control)**:
   - Thực thi các dependency kiểm tra quyền: `require_admin`, `require_editor_or_above`, `require_active_user`.
   - Endpoint đổi mật khẩu người dùng cá nhân: `POST /api/v1/auth/change-password`.
   - Giới hạn quyền `viewer`: Chỉ đọc dự án và tải file, không được submit job tổng hợp âm thanh.
2. **Hạn chế đăng nhập dò quét (Login Rate Limiter)**:
   - Chặn IP/User sau 5 lần đăng nhập thất bại liên tiếp trong 15 phút.
3. **Bộ lập lịch công bằng (Fair-Share Scheduling)**:
   - Nâng cấp `DurableQueueService.claim_next_job`: Thay vì FIFO đơn thuần, sắp xếp ứng viên ưu tiên theo vòng lặp người dùng (Per-User Round-Robin), đảm bảo người dùng có ít job đang chạy được ưu tiên xử lý trước người dùng đang chạy hàng loạt.
4. **Hạn mức lưu trữ người dùng (Storage Quotas)**:
   - Bổ sung cấu hình `USER_STORAGE_QUOTA_MB: int = 5120` (5GB/user).
   - Kiểm tra dung lượng trước khi lưu tệp âm thanh; từ chối với HTTP 413 `USER_STORAGE_QUOTA_EXCEEDED` khi vượt ngưỡng.

### Milestone 5B: Tích Hợp Local Reverse Proxy & HTTPS/TLS Đầu Mạng LAN
1. **Lựa chọn Reverse Proxy**: Sử dụng **Caddy Server** (khuyến nghị số 1 cho Windows vì là single binary nhẹ, hiệu năng cực cao, tích hợp sẵn Local HTTPS CA tự động cấp chứng chỉ không cần cấu hình phức tạp).
2. **Cấu hình Caddyfile Chuẩn Phòng Thu**:
   - Tự động sinh chứng chỉ nội bộ cho hostname LAN (ví dụ: `studio.local` hoặc IP `192.168.1.x`).
   - Phục vụ trực tiếp tệp tĩnh `apps/web/dist` với HTTP/2 và gzip/zstd nén nhanh.
   - Chuyển tiếp `/api/*` về `http://127.0.0.1:8765`.
   - Bật HSTS, CSP, X-Frame-Options và CORS header chặt chẽ.
3. **Cung cấp Script cài đặt chứng chỉ Root CA** cho máy khách Windows/macOS trong mạng LAN (`scripts/install_lan_cert.ps1`).

### Milestone 5C: Quản Lý Vòng Đời Tiến Trình Windows & Tự Động Khởi Động (Windows Service / Autostart)
1. **Kiến trúc dịch vụ trên Windows**:
   - Sử dụng **WinSW (Windows Service Wrapper)** mã nguồn mở để đăng ký 2 dịch vụ Windows độc lập:
     - `AIVoiceStudio_API`: Chạy FastAPI Server (`uvicorn apps.server.src.main:app`).
     - `AIVoiceStudio_Runner`: Chạy Standalone Scheduler (`python -m apps.server.src.runner`).
2. **Phục hồi sự cố mất điện (Power-Loss & Restart Recovery)**:
   - Cấu hình dịch vụ `Restart on Failure` (tự khởi động lại sau 10 giây nếu bị dừng đột ngột).
   - Cơ chế khởi động tự động quét sạch các khóa lease mồ côi (`recover_on_startup`).
3. **Bộ script quản trị vận hành một chạm (One-Click Management Scripts)**:
   - `scripts/service_install.ps1`: Cài đặt dịch vụ Windows.
   - `scripts/service_start.ps1`: Khởi động toàn bộ cụm dịch vụ.
   - `scripts/service_stop.ps1`: Dừng an toàn toàn bộ cụm dịch vụ.
   - `scripts/service_uninstall.ps1`: Gỡ bỏ sạch sẽ dịch vụ.

### Milestone 5D: Bộ Công Cụ Sao Lưu Toàn Diện, Giám Sát Vận Hành & Kiểm Thử Nghiệm Thu (Ops & Multi-User Testing)
1. **Bộ sao lưu & Phục hồi thảm họa toàn diện (Full Application-Data Backup)**:
   - Mở rộng `apps/server/src/backup.py` thành công cụ sao lưu toàn diện:
     - Bước 1: SQLite Online Backup `studio.db` -> snapshot `.db` với `PRAGMA integrity_check`.
     - Bước 2: Đồng bộ gia số thư mục `artifacts/` và `assets/` vào thư mục backup tương ứng.
     - Bước 3: Đóng gói metadata manifest chứa mã băm SHA-256 của toàn bộ tệp.
   - Kịch bản khôi phục độc lập `backup.py restore <backup_id> --force` kiểm tra tính toàn vẹn trước khi ghi đè.
2. **Endpoint Giám sát sức khỏe & Số liệu (Health & Metrics API)**:
   - `GET /api/v1/health`: Kiểm tra kết nối DB, tình trạng supervisor, bộ nhớ đĩa còn trống.
   - `GET /api/v1/metrics`: Báo cáo số lượng job theo trạng thái, số GPU/CPU slot đang dùng, dung lượng lưu trữ của từng user (Admin-only).
3. **Bộ kiểm thử tự động nhiều người dùng (Multi-User Automated E2E Suite)**:
   - Kịch bản mô phỏng 3 phiên làm việc đồng thời: 1 Admin, 1 Editor tiếng Việt, 1 Editor tiếng Trung.
   - Kiểm tra cách ly dữ liệu, công bằng hàng đợi, và không rò rỉ token qua mạng LAN.

---

## 5. ĐÁNH GIÁ NĂNG LỰC PHẦN CỨNG MÁY TRẠM (HARDWARE CAPACITY ASSESSMENT)

- **Cấu hình máy trạm vật lý**:
  - CPU: Intel Core i5-12400F (6 Cores, 12 Threads, Base 2.5GHz, Boost 4.4GHz).
  - RAM: 16GB DDR4.
  - GPU: NVIDIA GeForce RTX 3050 (6GB VRAM, Ampere).
  - Ổ cứng: SSD NVMe lưu trữ hệ điều hành và `D:\AIVoiceStudioData`.

- **Mô hình định lượng tải tối đa (Capacity Matrix)**:

| Thành phần | Tiêu thụ tài nguyên thực tế | Ngưỡng an toàn tối đa trên máy trạm | Ranh giới vận hành Phase 5 |
| :--- | :--- | :--- | :--- |
| **Qwen3-TTS Worker** | 3.8GB VRAM, ~1.2GB System RAM | 6.0GB VRAM tối đa của GPU | **Cố định duy nhất 1 GPU Slot**. Nghiêm cấm chạy 2 job GPU đồng thời (nguy cơ OOM 100%). |
| **VieNeu-TTS Worker** | 0GB VRAM, ~1.5GB System RAM, 2-3 CPU threads | 16GB RAM, 12 CPU threads | **Giữ tối đa 1 CPU Slot** (để dành 9 threads cho OS, Web API và FFmpeg DSP). |
| **FFmpeg DSP Mastering** | 0GB VRAM, ~0.5GB System RAM, 4 CPU threads | Chạy trong thời gian ngắn (5–15s) | Chạy tuần tự theo yêu cầu export, timeout 300s. |
| **FastAPI + Caddy Server** | ~0.3GB System RAM, < 1% CPU | Rất nhẹ, xử lý được 100+ req/s | Phục vụ tốt 5–10 người dùng nội bộ đồng thời. |
| **Tổng tải khi đỉnh điểm** | **3.8GB / 6GB VRAM (63%)**, **~5.5GB / 16GB RAM (34%)** | **Dư 2.2GB VRAM và 10.5GB RAM dự phòng an toàn cho Windows OS.** |

---

## 6. MÔ HÌNH HIỂM HỌA AN NINH MẠNG LAN (THREAT MODEL & MITIGATION)

| Mối đe dọa (STRIDE) | Kịch bản rủi ro trên mạng LAN | Biện pháp giảm thiểu kiến trúc trong Phase 5 |
| :--- | :--- | :--- |
| **Spoofing (Giả mạo danh tính)** | Kẻ xấu trong LAN thử đoán mật khẩu người dùng để chiếm quyền. | Bắt buộc mật khẩu mạnh ($\ge 8$ ký tự, chữ hoa, số); Rate Limiter khóa IP sau 5 lần sai. |
| **Tampering (Can thiệp dữ liệu)** | Bắt gói tin không mã hóa (HTTP) trên Wi-Fi để sửa đổi kịch bản. | **Bắt buộc HTTPS/TLS**. Mọi kết nối HTTP thường bị Caddy tự động chuyển hướng 301 sang HTTPS. |
| **Repudiation (Chối bỏ trách nhiệm)** | Người dùng xóa hoặc sửa dự án của người khác rồi chối bỏ. | Ghi nhận **Audit Log** kèm `user_id`, `ip_address`, `timestamp`, `action` cho mọi thao tác ghi/xóa. |
| **Information Disclosure (Lộ lọt thông tin)** | Lộ token JWT qua URL query strings hoặc tiêu đề Referer. | Duy trì triệt để giải pháp Hotfix R2: Header-only auth, cấm tiệt `?token=`, Cache-Control `no-store`. |
| **Denial of Service (Từ chối dịch vụ)** | Một user spam hàng loạt job render làm nghẽn toàn bộ hàng đợi. | **Fair-Share Round-Robin Scheduler** + Giới hạn số job chờ (Max pending jobs per user = 20). |
| **Elevation of Privilege (Leo thang đặc quyền)** | User vai trò `viewer` cố gọi API tạo người dùng hoặc sửa dự án. | RBAC kiểm tra quyền nghiêm ngặt ở tầng FastAPI Router dependency (`require_admin`). |

---

## 7. CHIẾN LƯỢC KIỂM THỬ & QUY TRÌNH ROLLBACK (TEST & ROLLBACK STRATEGY)

### 7.1. Chiến lược kiểm thử tự động
1. **Tier 1: Fast Security & RBAC Unit Tests** (< 5s): Kiểm thử từ chối quyền của viewer, khóa tài khoản sai mật khẩu, kiểm tra hạn mức lưu trữ quota.
2. **Tier 2: Multi-User Concurrency & Fairness Tests** (< 30s): Kiểm thử 2 người dùng gửi đồng thời 10 jobs; xác minh thuật toán Fair-Share xen kẽ công bằng giữa 2 người dùng.
3. **Tier 3: Full Browser E2E Suite trên mạng LAN mô phỏng** (< 60s): Sử dụng Playwright kiểm thử truy cập qua HTTPS nội bộ với 2 context trình duyệt riêng biệt đại diện cho 2 người dùng khác nhau.
4. **Tier 4: Disaster Recovery Test**: Chạy backup, xóa giả định một bảng hoặc tệp artifact, chạy restore và xác minh tính toàn vẹn 100%.

### 7.2. Quy trình Rollback dự phòng (Rollback Procedure)
Nếu có bất kỳ sự cố không lường trước nào xảy ra trong quá trình triển khai Phase 5:
1. Dừng các dịch vụ Windows: `scripts/service_stop.ps1`.
2. Khôi phục cơ sở dữ liệu về snapshot Phase 4: `python -m apps.server.src.backup restore studio_20261008_173037.db --force`.
3. Khôi phục cấu hình mạng về cục bộ: Thiết lập `HOST=127.0.0.1` trong `.env`.
4. Git rollback về commit cơ sở: `git checkout 24b3102`.
5. Hệ thống ngay lập tức quay trở lại trạng thái máy trạm đơn lẻ an toàn tuyệt đối của Phase 4.

---

## 8. BẢNG KIỂM PHÊ DUYỆT CỦA PRODUCT OWNER (APPROVAL CHECKLIST)

Trước khi bắt đầu bất kỳ dòng mã nguồn nào của Phase 5, **Product Owner phải tích chọn xác nhận phê duyệt**:

- [ ] **Mục 1**: Đồng ý với mục tiêu vận hành máy trạm nội bộ mạng LAN và từ chối mở Internet trong Phase 5.
- [ ] **Mục 2**: Đồng ý với phương án sử dụng **Local Reverse Proxy (Caddy Server)** với HTTPS/TLS nội bộ, giữ nguyên FastAPI trên `127.0.0.1:8765`.
- [ ] **Mục 3**: Đồng ý với nguyên tắc giữ nguyên giới hạn cứng **1 GPU Slot duy nhất** để bảo vệ an toàn cho card đồ họa NVIDIA RTX 3050 (6GB VRAM).
- [ ] **Mục 4**: Đồng ý áp dụng thuật toán điều phối công bằng **Fair-Share Scheduler** và hạn mức đĩa **User Storage Quotas (5GB/user)**.
- [ ] **Mục 5**: Phê duyệt 3 quyết định kiến trúc dự thảo: ADR-0010 (Reverse Proxy & TLS), ADR-0011 (RBAC & Fairness), ADR-0012 (Windows Process Lifecycle).
- [ ] **Mục 6**: **CẤP PHÉP CHÍNH THỨC** cho phép bắt đầu thi công Milestone 5A.

---

*Hồ sơ kế hoạch được lập tuân thủ nghiêm ngặt theo quy chuẩn [docs/GOVERNANCE.md](file:///d:/C/Dev/du%20an/TTS/docs/GOVERNANCE.md).*
