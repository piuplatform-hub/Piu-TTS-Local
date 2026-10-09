---
id: ADR-0011
title: Multi-User Role-Based Access Control, Storage Quotas & Fair-Share Scheduling
status: proposed
decision_authority: Product Owner
owner: Application Security Lead & Principal Software Architect
created: 2026-10-09
updated: 2026-10-09
related: [ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0009]
---

# Decision record: ADR-0011: Multi-User Role-Based Access Control, Storage Quotas & Fair-Share Scheduling

## Background / problem
Trong các giai đoạn trước, hệ thống phục vụ mục đích kiểm thử máy trạm cá nhân, nên việc điều phối hàng đợi `DurableJobScheduler` được thiết kế theo cơ chế FIFO có xét độ ưu tiên: `order_by(JobRecord.priority.desc(), JobRecord.queued_at.asc())`.

Khi chuyển sang môi trường nhiều người dùng qua mạng LAN:
1. **Nguy cơ chiếm dụng độc quyền tài nguyên (Resource Starvation)**: Người dùng A tải lên một chương sách dài gồm 100 phân đoạn và bấm tổng hợp hàng loạt. Vì GPU NVIDIA RTX 3050 (6GB) chỉ có thể chạy đúng 1 tác vụ tại một thời điểm (`max_gpu_slots = 1`), toàn bộ 100 tác vụ của Người dùng A sẽ chiếm trọn GPU trong 30–45 phút. Người dùng B chỉ cần tổng hợp thử một câu thoại ngắn 3 giây sẽ bị kẹt lại phía sau, dẫn đến tê liệt trải nghiệm làm việc nhóm.
2. **Nguy cơ cạn kiệt ổ cứng & Đua tranh hạn ngạch (Disk Exhaustion & Quota Race Conditions)**: Không có hạn mức lưu trữ, người dùng có thể làm đầy ổ đĩa `D:\AIVoiceStudioData`. Đồng thời, nếu tính toán hạn ngạch thụ động sau khi ghi tệp, hai yêu cầu đồng thời có thể gây vượt hạn ngạch (over-commitment).
3. **Phân quyền truy cập chưa chặt chẽ & Nguy cơ lộ mẫu giọng cá nhân**: Quyền hạn `viewer` và `editor` chưa được kiểm tra đồng bộ; nguy cơ Admin vô tình hoặc cố ý sử dụng mẫu giọng tham chiếu của người dùng khác.

## Scope and exclusions
- **Trong phạm vi:**
  - Nâng cấp bộ lập lịch `DurableQueueService` áp dụng thuật toán **4-Tier Fair-Share Anti-Starvation Scheduling** với bảng trạng thái bền vững `user_scheduling_states`.
  - Thiết lập **User Storage Quota** (mặc định 2,048 MB = 2 GB cho người dùng thông thường) đi kèm cơ chế **Two-Phase Atomic Storage Reservation** (`storage_reservations`).
  - Hỗ trợ **Bounded Progressive Batch Submission** để tương thích với các kịch bản dài tập vượt quá giới hạn 25 active jobs.
  - Phân định rõ 3 vai trò: `admin`, `editor`, `viewer` trên mọi endpoint biến đổi dữ liệu (Mutations).
  - Cách ly nghiêm ngặt quyền sở hữu tệp âm thanh tham chiếu giọng nói (`asset_rec.user_id == current_user.id`).
  - Cơ chế thu hồi phiên tức thì qua `token_version` khi đổi mật khẩu và chống dò quét mật khẩu theo bộ đôi `(ip_address, username)`.
- **Ngoại trừ:** Không xây dựng hệ thống thanh toán hay tính phí phức tạp; duy trì sự tinh gọn cho quy mô phòng thu nội bộ.

## Architectural approach

### 1. Thuật toán điều phối công bằng đa tầng (4-Tier Anti-Starvation Fair-Share Scheduling)
Để giải quyết bài toán chống bỏ đói khi phần cứng chỉ có 1 GPU slot khả dụng:
- **Tầng 1 (Head-of-Line Priority Precedence):** Ưu tiên các job có `priority` cao hơn (`JobRecord.priority DESC`).
- **Tầng 2 (In-flight Active Burden):** Ưu tiên người dùng đang có ít job chạy trên loại tài nguyên đó hơn (`RUNNING` / `PREPARING`).
- **Tầng 3 (Persistent Anti-Starvation Round-Robin):** Đối với các ứng viên có cùng in-flight burden (ví dụ khi slot vừa giải phóng và active count của tất cả người dùng đều bằng 0), ưu tiên người dùng có `last_dispatched_at` trong bảng `user_scheduling_states` xa nhất trong quá khứ.
- **Tầng 4 (Intra-user FIFO):** Xếp theo thứ tự nộp của cùng một người dùng (`queued_at ASC`).
- Cập nhật nguyên tử: Khi một job được nhận (`claim`), hệ thống cập nhật `last_dispatched_at = now()` cho người dùng đó.
- Bounded Progressive Batch: Giới hạn tối đa `MAX_OUTSTANDING_JOBS_PER_USER = 25`. Khi nộp batch dài tập (ví dụ 30–100 segments), các segment vượt trần được chuyển về `"pending"` và được tự động bơm vào hàng đợi khi các job trước hoàn thành.

### 2. Quản lý hạn ngạch nguyên tử 2 pha (Two-Phase Atomic Storage Reservation)
- Bảng `storage_reservations` quản lý vòng đời dung lượng:
  - **Pha 1 (Reserve):** Tính toán `Dung lượng thực tế + Dung lượng đang đặt trước active`. Nếu vượt `users.storage_quota_mb` (2048 MB), từ chối ngay với HTTP 413. Nếu còn chỗ, tạo reservation `ACTIVE` với thời hạn 30 phút.
  - **Pha 2 (Commit / Release):** Chuyển reservation sang `COMMITTED` khi tệp được sinh hoàn tất hoặc giải phóng (`RELEASED`) trong khối `finally` nếu tác vụ thất bại/bị hủy.

### 3. Ma trận phân quyền (RBAC Matrix)

| Vai trò (Role) | Xem dự án & Nghe âm thanh | Tạo/Sửa kịch bản & Render TTS | Xuất bản Master DSP | Upload & Dùng Voice Asset | Quản lý người dùng & Động cơ AI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Viewer** | Cho phép | Bị từ chối (403) | Bị từ chối (403) | Bị từ chối (403) | Bị từ chối (403) |
| **Editor** | Cho phép | Cho phép (Dự án riêng) | Cho phép | Chỉ dùng Asset của mình | Bị từ chối (403) |
| **Admin** | Cho phép | Cho phép (Toàn bộ) | Cho phép | **Chỉ dùng Asset của mình** | Cho phép (Độc quyền) |

## Risks / security / operations
- **Bảo toàn phần cứng:** Cơ chế 1 GPU slot và 1 CPU slot ngăn chặn hoàn toàn nguy cơ sập worker hoặc tràn VRAM (CUDA OOM).
- **Ngắt ngang tác vụ (Non-Preemptive):** Thuật ngữ được chuẩn hóa thành Head-of-Line Priority Precedence; tác vụ mạng nơ-ron đang chạy trên GPU không bị ngắt ngang để tránh lãng phí tài nguyên tính toán.

## Acceptance & evidence
- [x] Khi Người dùng A nộp 25 jobs và Người dùng B nộp 1 job ngay sau đó, job của Người dùng B được thực thi ngay ở lượt thứ 2 (A1 $\to$ B1 $\to$ A2), loại bỏ hoàn toàn starvation.
- [x] Hai yêu cầu đồng thời 80MB trên hạn ngạch 100MB được phân định nguyên tử: đúng 1 thành công, 1 bị từ chối với HTTP 413, không xảy ra over-commit.
- [x] Đổi mật khẩu tài khoản lập tức thu hồi toàn bộ token cũ với HTTP 401 `TOKEN_REVOKED`.
- [x] Dò mật khẩu sai 5 lần trên 1 tài khoản chỉ khóa tài khoản đó, không gây ảnh hưởng đến tài khoản khác trên cùng IP.
- [x] Kịch bản dài tập 30 phân đoạn nộp thành công thông qua progressive batching, không phát sinh lỗi 429.
- [x] Tài khoản `viewer` bị chặn 403 trên toàn bộ mutations. Admin bị chặn 403 khi dùng voice asset của user khác.

## Decision / outcome / follow-up
- **Trạng thái:** **Proposed (Chờ Product Owner phê duyệt chính thức trước khi bắt đầu Phase 5B)**.
- **Kế hoạch liên quan:** [PHASE_05_DEPLOYMENT_SECURITY.md](../../plans/PHASE_05_DEPLOYMENT_SECURITY.md).
