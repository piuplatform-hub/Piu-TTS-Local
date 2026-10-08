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
2. **Nguy cơ cạn kiệt ổ cứng (Disk Exhaustion)**: Không có hạn mức lưu trữ, người dùng có thể tải lên các tệp âm thanh tham chiếu mẫu dung lượng lớn hoặc xuất bản hàng trăm tệp Master WAV PCM không nén, làm đầy ổ đĩa `D:\AIVoiceStudioData`.
3. **Phân quyền truy cập chưa chặt chẽ**: Quyền hạn `viewer` và `editor` chưa được kiểm tra đồng bộ trên tất cả các API nghiệp vụ.

## Scope and exclusions
- **Trong phạm vi:**
  - Nâng cấp bộ lập lịch `DurableJobScheduler` áp dụng thuật toán **Fair-Share Round-Robin**: Xen kẽ thực thi nhiệm vụ giữa các người dùng khác nhau trong hàng đợi.
  - Thiết lập **User Storage Quota** (mặc định 5GB dung lượng tệp âm thanh hoặc 30 dự án cho mỗi tài khoản).
  - Phân định rõ 3 vai trò: `admin`, `editor`, `viewer` trên mọi endpoint.
  - Bổ sung cơ chế chống dò quét mật khẩu (Login Rate Limiter).
- **Ngoại trừ:** Không xây dựng hệ thống thanh toán hay tính phí phức tạp; duy trì sự tinh gọn cho quy mô phòng thu nội bộ.

## Proposed approach / options

### 1. Thuật toán điều phối công bằng (Fair-Share Scheduling)
- Thay vì lấy 10 jobs đầu tiên thuần túy theo thời gian xếp hàng, truy vấn chọn lọc nhóm các jobs `queued` và ưu tiên cấp lượt cho người dùng có **số lượng job đang chạy (`RUNNING`) ít nhất**.
- Nếu cả Người dùng A và Người dùng B đều có job chờ, hệ thống sẽ thực thi luân phiên: 1 job của A -> 1 job của B -> 1 job của A -> 1 job của B.
- Giới hạn tối đa số lượng job chờ kích hoạt cho mỗi người dùng: `MAX_PENDING_JOBS_PER_USER = 25`.

### 2. Kiểm soát hạn mức lưu trữ (Per-User Storage Quota)
- Trước khi tạo bản ghi Artifact (`ArtifactService.create_artifact_from_bytes`) hoặc Master Export, hệ thống tính toán tổng dung lượng tệp hiện có thuộc sở hữu của người dùng.
- Nếu vượt quá `USER_STORAGE_QUOTA_MB` (5,120 MB), API từ chối với HTTP 413 và thông báo: `USER_STORAGE_QUOTA_EXCEEDED: Vui lòng xóa bớt các phiên bản âm thanh cũ`.

### 3. Ma trận phân quyền (RBAC Matrix)

| Vai trò (Role) | Xem dự án & Nghe âm thanh | Tạo/Sửa kịch bản & Render TTS | Xuất bản Master DSP | Quản lý người dùng & Động cơ AI |
| :--- | :---: | :---: | :---: | :---: |
| **Viewer** | Cho phép | Bị từ chối (403) | Bị từ chối (403) | Bị từ chối (403) |
| **Editor** | Cho phép | Cho phép (Dự án riêng) | Cho phép | Bị từ chối (403) |
| **Admin** | Cho phép | Cho phép (Toàn bộ) | Cho phép | Cho phép (Độc quyền) |

## Risks / security / operations
- **Độ phức tạp câu lệnh SQL**: Truy vấn Fair-Share có thể tốn thêm vài mili-giây so với câu lệnh `LIMIT 1` đơn giản. Tuy nhiên với SQLite chạy trên SSD NVMe và quy mô phòng thu < 10 người dùng, độ trễ truy vấn tăng không quá 2ms, hoàn toàn không ảnh hưởng tới hiệu năng tổng thể.

## Acceptance & evidence
- [ ] Khi Người dùng A nộp 5 jobs và Người dùng B nộp 1 job ngay sau đó, job của Người dùng B được thực thi ngay ở lượt thứ 2, không phải chờ cả 5 jobs của A hoàn tất.
- [ ] Người dùng vượt quá hạn mức 5GB bị từ chối tạo tệp mới với mã lỗi HTTP 413 rõ ràng.
- [ ] Tài khoản vai trò `viewer` bị từ chối khi gọi API `render-batch` hoặc `render`.

## Decision / outcome / follow-up
- **Trạng thái:** **Proposed (Chờ Product Owner phê duyệt)**.
- **Kế hoạch liên quan:** [PHASE_05_DEPLOYMENT_SECURITY.md](../../plans/PHASE_05_DEPLOYMENT_SECURITY.md).
