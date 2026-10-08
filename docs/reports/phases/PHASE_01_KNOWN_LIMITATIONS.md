# AI VOICE STUDIO — GIỚI HẠN KỸ THUẬT GIAI ĐOẠN PHASE 1
**Phiên bản tài liệu:** Phase 1 Baseline  
**Ngày phát hành:** 2026-10-08  
**Mục đích:** Ghi nhận minh bạch các giới hạn kỹ thuật của Phase 1 nhằm ngăn chặn việc hiểu lầm hoặc giả định sai về năng lực của hệ thống trước khi bước vào các giai đoạn tiếp theo.

---

## 1. GIỚI HẠN VỀ ENGINE VÀ TRỌNG SỐ AI

### 1.1. Chỉ sử dụng Mock Contract Engine
- Hệ thống Phase 1 sử dụng **Contract Mock Engine** (`engines/mock`) để kiểm thử tích hợp hợp đồng phần mềm, API và giao diện.
- **Không có trọng số neural thực tế nào được tải:** VieNeu-TTS và Qwen3-TTS chưa được cài đặt hay tải về trong Phase 1. File âm thanh được sinh ra là sóng âm điều biến tổng hợp thuật toán PCM 16-bit nhằm kiểm chứng đường ống dữ liệu, codec WAV và giao diện phát âm thanh.
- **Giai đoạn giải quyết:** Giai đoạn Phase 1B (Benchmark & Spike) và Phase 3 (Neural Integration).

---

## 2. GIỚI HẠN VỀ LẬP LỊCH VÀ KHẢ NĂNG PHỤC HỒI (DURABLE SCHEDULING)

### 2.1. Chưa có bộ phục hồi tác vụ bền vững sau sự cố sập nguồn (Durable Crash Recovery)
- Trong Phase 1, các tác vụ được đưa vào hàng đợi SQLite và kích hoạt phi đồng bộ bằng `asyncio.create_task()`.
- Nếu máy chủ bị tắt đột ngột (mất điện, kill process backend) khi một job đang ở trạng thái `running`, job đó sẽ giữ nguyên trạng thái `running` trong cơ sở dữ liệu và không tự động được một daemon quét lại để gán nhãn `failed` hoặc thực thi lại.
- **Giai đoạn giải quyết:** Giai đoạn Phase 2 (Durable SQLite Queue & Worker Lease Daemon).

### 2.2. Giới hạn đồng thời (Concurrency Cap)
- Phase 1 cấu hình mặc định giới hạn xử lý đồng thời 1 tác vụ CPU tại một thời điểm (`MAX_CONCURRENT_CPU_JOBS = 1`) để bảo đảm an toàn tài nguyên máy phát triển.

---

## 3. GIỚI HẠN VỀ MẠNG VÀ PHÂN QUYỀN

### 3.1. Chỉ liên kết Loopback Cục bộ (Localhost Only)
- Máy chủ backend chỉ liên kết với địa chỉ IP `127.0.0.1:8765`.
- Không hỗ trợ truy cập qua mạng LAN nội bộ hoặc Internet bên ngoài.
- Không có cấu hình HTTPS/TLS cục bộ (vì chỉ phục vụ qua loopback).

### 3.2. Mô hình Quản lý Người dùng trên Giao diện (User Management UI)
- Mặc dù API phân quyền RBAC và tạo người dùng (`POST /api/v1/auth/users`) đã được xây dựng và kiểm thử hoàn chỉnh tại tầng backend, giao diện Web Phase 1 hiện tại tập trung phục vụ luồng làm việc của quản trị viên (Single-Admin Studio Workflow).
- Giao diện quản lý danh sách tài khoản, đổi mật khẩu và phân quyền trực quan trên Web UI sẽ được mở rộng trong Phase 4/Phase 5.

---

## 4. GIỚI HẠN VỀ NỀN TẢNG DESKTOP

### 4.1. Ứng dụng chạy trên Trình duyệt Web (Web-First)
- Hệ thống hoạt động qua trình duyệt web trên `http://127.0.0.1:8765`.
- Chưa tích hợp vỏ bọc máy tính để bàn dạng Native Desktop (Tauri / Electron) hoặc Windows Tray Service.
- **Giai đoạn giải quyết:** Phase 4 (Native Desktop Wrapper).

---

## 5. RANH GIỚI CÔ LẬP TIẾN TRÌNH (PROCESS ISOLATION BOUNDARIES)

### 5.1. Windows Job Objects không thay thế Container/Hypervisor Sandbox
- Process Supervisor sử dụng Windows Job Objects với cờ `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` để đảm bảo dọn dẹp sạch sẽ vòng đời tiến trình, ngăn chặn tuyệt đối tiến trình zombie rò rỉ cổng mạng.
- Tuy nhiên, đây là cơ chế quản lý vòng đời hệ điều hành, không phải môi trường sandbox ảo hóa (không hạn chế quyền đọc/ghi tệp hệ thống của người dùng hiện tại). Các worker chạy dưới quyền tài khoản người dùng Windows thông thường.
- Kiến trúc đảm bảo sự ổn định khi worker sập (crash isolation), nhưng việc chạy các model không rõ nguồn gốc (untrusted code) vẫn bị nghiêm cấm theo quy định bảo mật ADR-0005.
