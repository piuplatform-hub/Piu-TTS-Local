# AI Voice Studio — Đánh Giá An Ninh Giai Đoạn 5A (Phase 5A Security Review)

**Vai trò:** Senior Application Security Engineer & Independent Security Reviewer  
**Kết quả đánh giá:** **SECURITY PASS** (Phê duyệt kiểm soát an ninh đa người dùng cho Milestone 5A)  
**Ngày đánh giá:** 09/10/2026  
**Commit cơ sở:** `a9e4f7e`  
**Phạm vi:** Kiểm toán an ninh mã nguồn lõi cho môi trường đa người dùng (Localhost `127.0.0.1` only).

---

## 1. MỤC TIÊU VÀ PHẠM VI KIỂM TOÁN AN NINH

Kiểm toán an ninh Milestone 5A nhằm bảo đảm nền tảng AI Voice Studio được gia cố toàn diện trước các lỗ hổng xác thực, phân quyền và cạn kiệt tài nguyên trước khi xem xét mở rộng sang môi trường mạng nội bộ (LAN). Toàn bộ quá trình kiểm toán được thực hiện theo tiêu chuẩn OWASP ASVS và CWE Top 25.

---

## 2. PHÂN TÍCH RỦI RO VÀ GIẢI PHÁP GIA CỐ KỸ THUẬT

### 2.1. Phân quyền và Ủy quyền Tiêu cực (CWE-285 / CWE-862: Missing Authorization)
- **Hiện trạng trước 5A:** Một số endpoint tạo/sửa segment hoặc submit job chỉ phụ thuộc vào token xác thực mà chưa phân biệt rõ ràng vai trò `viewer` hay `editor`.
- **Giải pháp gia cố:**
  - Thiết lập ma trận RBAC chặt chẽ: `require_editor` trở thành dependency bắt buộc trên mọi route mutation (POST/PUT/DELETE) tại:
    - `apps/server/src/api/v1/projects.py`
    - `apps/server/src/api/v1/jobs.py`
    - `apps/server/src/api/v1/assets.py`
  - Người dùng có vai trò `viewer` bị từ chối ngay lập tức với mã lỗi `HTTP 403 Forbidden` (`FORBIDDEN_INSUFFICIENT_PERMISSIONS`) khi cố gắng chỉnh sửa dự án, kịch bản, nhân vật, render âm thanh hoặc tải lên asset.
  - Endpoint `POST /auth/users` từ chối người dùng thông thường (`FORBIDDEN_USER_CREATION`), loại bỏ khả năng tự ý nhân bản tài khoản.

### 2.2. Ngăn Ngừa Lạm Quyền Mẫu Giọng Cá Nhân (CWE-639: Insecure Direct Object References)
- **Hiện trạng trước 5A:** Khi gửi job nhân bản giọng nói với `ref_audio_asset_id`, hệ thống cho phép tài khoản Admin sử dụng asset của bất kỳ ai mà không kiểm tra quyền sở hữu.
- **Giải pháp gia cố:**
  - Trong `DurableQueueService.submit_speech_job`: Áp dụng quy tắc kiểm tra nghiêm ngặt: `asset_rec.user_id == current_user.id`.
  - Tuyệt đối không cho phép đặc quyền Admin bypass logic này. Bất kỳ nỗ lực nào nhằm tham chiếu đến mẫu giọng của người khác đều bị chặn đứng với `HTTP 403 Forbidden` (`FORBIDDEN_ASSET_ACCESS`).

### 2.3. Phòng Chống Tấn Công Từ Chối Dịch Vụ Qua Dung Lượng Lưu Trữ (CWE-400: Uncontrolled Resource Consumption)
- **Hiện trạng trước 5A:** Chưa có cơ chế giới hạn dung lượng lưu trữ trên từng tài khoản, người dùng có thể gửi âm thanh liên tục dẫn đến cạn kiệt ổ đĩa máy chủ.
- **Giải pháp gia cố:**
  - Thêm trường `storage_quota_mb` vào bảng `users` (mặc định 2048 MB = 2 GB).
  - Triển khai `UserQuotaService` hạch toán chính xác tổng kích thước các tệp `artifacts`, `master_exports`, và `assets` thuộc quyền sở hữu của người dùng.
  - Kiểm tra quota trước khi upload reference, trước khi render speech, và trước khi xuất master export. Nếu vượt quá hạn ngạch, từ chối với `HTTP 413 Payload Too Large` (`USER_STORAGE_QUOTA_EXCEEDED`).
  - Đảm bảo cơ chế dọn dẹp nguyên tử (Atomic cleanup): Trong trường hợp tiến trình ghép nối master export thất bại hoặc vượt quota, tệp tạm trên đĩa được dọn dẹp lập tức, ngăn ngừa rò rỉ dung lượng ổ đĩa.

### 2.4. Ngăn Chặn Độc Chiếm Hàng Đợi (Queue Starvation & Denial of Service)
- **Hiện trạng trước 5A:** Thuật toán hàng đợi chỉ dựa trên FIFO và priority, cho phép một người dùng gửi hàng trăm job làm nghẽn toàn bộ hệ thống.
- **Giải pháp gia cố:**
  - Áp dụng trần tối đa `MAX_OUTSTANDING_JOBS_PER_USER = 25`. Người dùng gửi job thứ 26 trở đi sẽ nhận mã lỗi `HTTP 429 Too Many Requests` (`TOO_MANY_OUTSTANDING_JOBS`).
  - Cải tiến `DurableQueueService.claim_next_job`: Trong cùng một nhóm ưu tiên (`priority`), thuật toán lựa chọn người dùng theo nguyên tắc **Least-Active-User-First** (người có ít job in-flight nhất sẽ được ưu tiên nhận slot CPU hoặc GPU).
  - Giữ vững tính bất biến độc quyền phần cứng: 1 GPU slot (RTX 3050) và 1 CPU slot, ngăn chặn triệt để xung đột VRAM hoặc treo hệ thống.

### 2.5. Phòng Chống Dò Quét Mật Khẩu & Thu Thập Tài Khoản (CWE-307 & CWE-204)
- **Hiện trạng trước 5A:** Đăng nhập sai nhiều lần chưa bị khóa theo thời gian trượt (Sliding Window Lockout).
- **Giải pháp gia cố:**
  - Bổ sung bảng `login_attempts` ghi nhận các lượt đăng nhập thất bại.
  - Triển khai `LoginProtectionService` với cơ chế cửa sổ trượt 15 phút. Nếu phát hiện $\ge 5$ lần thất bại từ cùng một username hoặc một IP, khóa tạm thời và trả về `HTTP 429 Too Many Requests` (`TOO_MANY_LOGIN_ATTEMPTS`) kèm header `Retry-After: 900`.
  - Bảo vệ chống user enumeration: Thông điệp phản hồi đăng nhập sai luôn là `"Incorrect username or password."` bất kể username có tồn tại hay không.
  - Quy trình đổi mật khẩu an toàn: Bắt buộc xác minh mật khẩu hiện tại và kiểm tra độ dài mật khẩu mới $\ge 8$ ký tự.

---

## 3. RANH GIỚI BẢO MẬT & HẠN CHẾ TUÂN THỦ

1. **Ranh giới cục bộ (Localhost Boundary):**
   - Ứng dụng hiện vẫn chỉ lắng nghe trên `127.0.0.1`.
   - **Tuyệt đối chưa mở cổng ra 0.0.0.0, chưa cấu hình Windows Firewall, chưa cài đặt Caddy reverse proxy hay Windows Service.**
2. **Kế hoạch tiếp theo:**
   - Việc mở rộng ra mạng cục bộ (LAN) chỉ được phép tiến hành sau khi các ADR-0010, ADR-0011, ADR-0012 được phê duyệt chính thức tại các mốc Milestone 5B và 5C.

---

## 4. KẾT LUẬN

Milestone 5A đạt chuẩn an ninh toàn diện (**SECURITY PASS**). Tất cả các biện pháp gia cố đã được kiểm chứng qua 7 bài test an ninh mới và 78 bài test hồi quy tổng thể với tỷ lệ thành công 100%.
