# AI Voice Studio — Giới Hạn Đã Biết & Ranh Giới Vận Hành (Phase 5 Known Limitations)

**Giai đoạn áp dụng:** Phase 5A Release Gate R1  
**Môi trường:** Máy trạm cục bộ (Local Workstation `127.0.0.1`)  
**Ngày cập nhật:** 09/10/2026  
**Kiến trúc:** R1.1 Modular Monolith (SQLite WAL mode, Process-isolated Engine Workers)  

---

## 1. RANH GIỚI MẠNG VÀ PHẠM VI TRUY CẬP (NETWORK BOUNDARIES)

1. **Giới hạn Loopback tuyệt đối:**
   - Cả Backend API (Uvicorn, cổng 8000) và Frontend Web (Vite Dev / Static Server, cổng 5173) hiện tại chỉ được phép lắng nghe trên địa chỉ loopback cục bộ `127.0.0.1`.
   - Hệ thống **chưa được cấu hình lắng nghe trên `0.0.0.0`**, chưa mở cổng trên Windows Firewall, và chưa thể truy cập từ các thiết bị khác trong mạng nội bộ (LAN).
   - Việc mở rộng ra mạng LAN và thiết lập Reverse Proxy (Caddy) cùng chứng chỉ TLS tự ký thuộc phạm vi của **Phase 5B (chưa được phép kích hoạt)**.

2. **Chưa có lớp mã hóa đường truyền (No TLS on Localhost):**
   - Các kết nối nội bộ giữa trình duyệt và máy chủ backend trên `127.0.0.1` hiện đang sử dụng giao thức HTTP thuần túy.
   - Điều này chấp nhận được đối với môi trường máy trạm cá nhân khép kín, nhưng bắt buộc phải có TLS khi chuyển sang chia sẻ mạng LAN.

---

## 2. GIỚI HẠN TÀI NGUYÊN PHẦN CỨNG VÀ ĐẶC TÍNH SUY LUẬN (HARDWARE CONSTRAINTS)

1. **Đơn Slot Thực Thi Phần Cứng (Single Hardware Slot Serialization):**
   - Nhằm bảo vệ card đồ họa NVIDIA GeForce RTX 3050 (6GB VRAM) khỏi tình trạng tràn bộ nhớ (Out-Of-Memory / CUDA OOM), hệ thống cưỡng chế nghiêm ngặt:
     - `max_gpu_slots = 1`
     - `max_cpu_slots = 1`
   - Bất kể có bao nhiêu người dùng đang xếp hàng, tại một thời điểm chỉ có duy nhất 1 tác vụ suy luận thần kinh được chạy trên GPU và 1 tác vụ trên CPU.
   - Các tác vụ còn lại sẽ được điều phối công bằng theo thuật toán Round-Robin chống bỏ đói (Anti-Starvation Fair-Share), nhưng tổng thời gian hoàn thành sẽ phụ thuộc vào độ dài âm thanh của các tác vụ đi trước.

2. **Không Hỗ Trợ Ngắt Ngang Tác Vụ Mạng Nơ-ron Đang Chạy (Non-Preemptive Execution):**
   - Thuật ngữ kiến trúc chuẩn xác là **Head-of-Line Priority Precedence** (Ưu tiên đầu hàng đợi khi điều phối), không phải Preemptive Scheduling.
   - Một khi mô hình VieNeu-TTS hoặc Qwen3-TTS đã bắt đầu sinh âm thanh trong worker process, tác vụ đó không thể bị tạm dừng hay ngắt ngang để nhường chỗ cho một tác vụ ưu tiên cao hơn, vì điều này sẽ làm hỏng ngữ cảnh tensor và lãng phí toàn bộ chu kỳ tính toán đã thực hiện.
   - Tác vụ ưu tiên cao hơn sẽ được chọn thực thi ngay ở lượt giải phóng slot tiếp theo.

---

## 3. GIỚI HẠN HÀNG ĐỢI VÀ HẠN NGẠCH LƯU TRỮ (QUEUE & STORAGE BOUNDARIES)

1. **Ngưỡng Giới Hạn Tác Vụ Chờ Của Mỗi Người Dùng (Per-User Outstanding Jobs Limit):**
   - Mỗi tài khoản người dùng chỉ được phép duy trì tối đa `MAX_OUTSTANDING_JOBS_PER_USER = 25` tác vụ đang hoạt động đồng thời (ở các trạng thái `QUEUED`, `PREPARING`, `RUNNING`).
   - Đối với các kịch bản dài tập (ví dụ chương sách 50–100 phân đoạn), tính năng **Progressive Batch Submission** của `ProjectService` sẽ nộp tối đa 25 phân đoạn đầu tiên và giữ các phân đoạn còn lại ở trạng thái `"pending"`. Khi các tác vụ trước hoàn thành, các phân đoạn pending sẽ được tự động đưa vào hàng đợi. Người dùng không nên gửi nhiều batch dồn dập vượt quá khả năng xử lý của cơ sở dữ liệu.

2. **Cơ Chế Đặt Trước Hạn Ngạch Lưu Trữ (Storage Quota Reservation Window):**
   - Mỗi người dùng thông thường có hạn ngạch lưu trữ mặc định là 2048 MB (2 GB).
   - Khi gửi tác vụ, hệ thống tạo bản ghi đặt trước (`storage_reservations`) với dung lượng ước tính. Bản ghi này có thời hạn tự động hết hạn là 30 phút để tránh rò rỉ hạn ngạch ảo nếu hệ thống gặp sự cố bất ngờ.
   - Người dùng cần chủ động dọn dẹp các phiên bản âm thanh thô hoặc dự án cũ nếu tài khoản chạm ngưỡng 2 GB.

---

## 4. GIỚI HẠN VỀ CƠ SỞ DỮ LIỆU VÀ QUẢN LÝ TIẾN TRÌNH (DATABASE & LIFECYCLE)

1. **Quy Mô Phù Hợp của SQLite WAL:**
   - Cơ sở dữ liệu SQLite ở chế độ Write-Ahead Logging (WAL) hoạt động cực kỳ ổn định, tốc độ cao cho môi trường máy trạm phòng thu nội bộ với quy mô dưới 10 người dùng đồng thời.
   - Hệ thống không được thiết kế cho kiến trúc phân tán nhiều máy chủ (distributed multi-node clustering). Không được mở tệp `studio.db` qua các giao thức chia sẻ tệp mạng như SMB/NFS vì nguy cơ hỏng khóa tệp (file lock corruption).

2. **Quy Trình Sao Lưu Bắt Buộc:**
   - **Tuyệt đối không sử dụng lệnh sao chép tệp thô của hệ điều hành** (như `Copy-Item`, `cp`, `xcopy`) khi máy chủ Backend đang hoạt động.
   - Mọi hoạt động sao lưu cơ sở dữ liệu phải được thực hiện thông qua **SQLite Online Backup API CLI**:
     ```powershell
     sqlite3.exe "D:\AIVoiceStudioData\studio.db" ".backup 'D:\AIVoiceStudioData\backups\studio_YYYYMMDD_HHMMSS.db'"
     ```

3. **Vòng Đời Tiến Trình (Process Lifecycle):**
   - Hiện tại hệ thống chưa được tích hợp làm Windows Service (dự kiến trong Phase 5C).
   - Việc khởi động và dừng hệ thống cần thông qua các tập lệnh khởi chạy chuẩn của dự án trong cửa sổ terminal đang mở. Nếu cửa sổ lệnh bị đóng, tiến trình máy chủ sẽ dừng lại.
