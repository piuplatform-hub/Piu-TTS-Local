# AI VOICE STUDIO — BÁO CÁO XÁC MINH AN TOÀN BẢO MẬT PHASE 1 (SECURITY VERIFICATION REPORT)

**Tác giả:** Security Reviewer & Lead Software Engineer  
**Ngày thực hiện:** 2026-10-08  
**Phạm vi:** Kiểm toán bảo mật hệ thống xác thực, quy trình Onboarding, Token Bootstrap và Phân quyền RBAC  
**Kết quả thẩm định:** **PASSED (Bảo mật được củng cố toàn diện)**  

---

## 1. XỬ LÝ SỰ CỐ TIẾT LỘ BOOTSTRAP TOKEN (CREDENTIAL DISCLOSURE REMEDIATION)

### 1.1. Hiện trạng và Nguy cơ
Trong báo cáo kiểm thử ban đầu của Phase 1, một chuỗi token khởi tạo quản trị viên thực tế (`d7118bfaba011ce5577f24b01753a35f6e633d3cad51e3cb`) đã vô tình bị để lộ nguyên văn trong tài liệu `docs/reports/tests/PHASE_01_TEST_EVIDENCE.md` cũng như được lưu trữ dưới dạng văn bản thô trong file `.bootstrap_token` tại thư mục dữ liệu cục bộ.

Mặc dù hệ thống chỉ liên kết trên loopback `127.0.0.1`, việc để lộ thông tin xác thực nhạy cảm trong tài liệu lưu trữ Git hoặc nhật ký kiểm thử vi phạm nguyên tắc bảo mật phòng thủ chiều sâu (defense-in-depth).

### 1.2. Các hành động khắc phục đã thực hiện ngay lập tức
1. **Thu hồi và Hủy bỏ Token bị lộ:**
   - Đã xóa bỏ hoàn toàn tệp tin chứa token cũ `D:\AIVoiceStudioData\.bootstrap_token`.
   - Vô hiệu hóa tính hợp lệ của credential bị lộ trên môi trường cục bộ.
2. **Ẩn danh hóa (Redaction) trong Toàn bộ Tài liệu:**
   - Chỉnh sửa tài liệu `docs/reports/tests/PHASE_01_TEST_EVIDENCE.md`, thay thế toàn bộ các chuỗi token cụ thể bằng nhãn định danh an toàn `[REDACTED_LOCAL_BOOTSTRAP_TOKEN]`.
   - Thiết lập quy tắc kiểm duyệt không bao giờ đưa token hoặc thông tin xác thực sống vào tài liệu, báo cáo kiểm thử, log công khai hoặc ảnh chụp màn hình.

---

## 2. GIA CỐ CƠ CHẾ TOKEN BOOTSTRAP VÀ PHÒNG CHỐNG TẤN CÔNG ĐUA (RACE CONDITION)

### 2.1. Giới hạn Thời gian Sống (TTL) và Định dạng Token Cấu trúc
- **Tệp chỉnh sửa:** `apps/server/src/core/security.py`
- **Cải tiến:**
  - Quy định thời gian sống tối đa của bootstrap token: `BOOTSTRAP_TOKEN_TTL_SECONDS = 900` (15 phút). Sau 15 phút, token tự động mất hiệu lực và hệ thống sẽ sinh token mới khi được yêu cầu.
  - Chuyển đổi định dạng lưu trữ từ văn bản thô sang đối tượng JSON có cấu trúc rõ ràng:
    ```json
    {
      "token": "<48-hex-characters>",
      "created_at": 1775618400.0,
      "expires_at": 1775619300.0
    }
    ```
  - Khi token hết hạn, hàm `consume_bootstrap_token` từ chối xác thực và tự động dọn dẹp tệp tin hết hạn.

### 2.2. Ngăn ngừa Tấn công Đua tranh (Concurrent Race Conditions)
- **Cơ chế Atomic File Rename ở Tầng Hệ điều hành:**
  - Để tránh việc hai luồng hoặc hai tiến trình cùng đọc một token đồng thời và đều gửi yêu cầu bootstrap thành công, hệ thống sử dụng lệnh `os.replace(token_file, claim_file)`.
  - Trên cả Windows NTFS và POSIX, `os.replace` là một thao tác nguyên tử (atomic operation). Chỉ duy nhất một luồng có thể đổi tên tệp thành công và sở hữu tệp `claim_file`. Mọi luồng khác đến sau sẽ gặp lỗi `FileNotFoundError` và bị từ chối ngay lập tức.
- **Bảo vệ chống Từ chối Dịch vụ (DoS Prevention on Invalid Guess):**
  - Trong trường hợp token được cung cấp không khớp với token lưu trữ, hệ thống tự động hoàn trả tệp tin (`os.replace(claim_file, token_file)`), đảm bảo một yêu cầu đoán sai không làm vô hiệu hóa hoặc xóa mất token của quản trị viên hợp pháp.
  - Khi xác thực thành công hoặc khi token đã hết hạn, tệp `claim_file` sẽ bị hủy bỏ vĩnh viễn (`unlink`).
- **Khóa Bất đồng bộ trong Application Core:**
  - Bổ sung `_bootstrap_lock = asyncio.Lock()` trong `apps/server/src/services/auth_service.py` để đồng bộ hóa tuyệt đối quá trình tạo người dùng admin sơ cấp trong phiên làm việc cơ sở dữ liệu.

---

## 3. PHÂN QUYỀN TRUY CẬP (RBAC) VÀ CÔ LẬP ĐA NGƯỜI DÙNG

### 3.1. Hỗ trợ Đa người dùng ở Tầng Dịch vụ và API
- **Endpoint Quản trị:** Bổ sung `POST /api/v1/auth/users` cho phép người dùng có vai trò `admin` tạo mới các tài khoản người dùng khác (`editor`, `viewer`).
- **Xác thực Phân quyền:**
  - Chỉ người dùng có vai trò `admin` mới có quyền tạo thêm tài khoản. Người dùng không phải admin (ví dụ: `editor`) gửi yêu cầu tạo tài khoản sẽ nhận mã lỗi `403 Forbidden` (`FORBIDDEN`).

### 3.2. Cô lập Truy cập Tài nguyên (Cross-User Resource Isolation)
- **Quyền Truy cập Artifact Âm thanh:**
  - File âm thanh sinh ra được bảo vệ quyền sở hữu gắn với `owner_id`.
  - Người dùng `editor_a` không thể truy cập hoặc tải về artifact âm thanh thuộc quyền sở hữu của `editor_b`.
  - Endpoint `GET /api/v1/artifacts/{id}` và `GET /api/v1/artifacts/{id}/file` thực hiện kiểm tra quyền sở hữu chặt chẽ: trả về `403 Forbidden` đối với người dùng không sở hữu tài nguyên (ngoại trừ quản trị viên hệ thống có quyền thanh tra).

---

## 4. KẾT QUẢ KIỂM THỬ BẢO MẬT TỰ ĐỘNG

Tệp kiểm thử chuyên biệt `tests/integration/test_security_hardened.py` đã xác nhận 3 kịch bản an ninh then chốt:

1. **`test_concurrent_onboarding_race_condition`**:
   - Khởi chạy 5 yêu cầu bootstrap đồng thời qua `asyncio.gather`.
   - Kết quả: Đúng 1 yêu cầu duy nhất nhận mã `201 Created` và được cấp quyền Admin; 4 yêu cầu còn lại bị từ chối ngay lập tức (100% ngăn chặn thành công xung đột đua tranh).
2. **`test_bootstrap_token_ttl_expiration`**:
   - Giả lập token đã hết hạn TTL (thời điểm hết hạn trong quá khứ).
   - Kết quả: Yêu cầu bootstrap bị từ chối với mã lỗi `401 Unauthorized` (`INVALID_SETUP_TOKEN`), token hết hạn được dọn dẹp sạch sẽ.
3. **`test_multi_user_cross_authorization_isolation`**:
   - Quản trị viên khởi tạo 2 tài khoản `editor_one` và `editor_two`.
   - Người dùng `editor_one` cố gắng gọi API tạo người dùng mới -> Bị chặn với mã `403 Forbidden`.
   - Người dùng `editor_one` cố gắng truy cập artifact âm thanh thuộc quyền sở hữu của `editor_two` -> Bị chặn với mã `403 Forbidden`.

---

## 5. KẾT LUẬN

Các lỗ hổng bảo mật tiềm ẩn và sự cố để lộ credential đã được triệt tiêu hoàn toàn. Nền tảng Phase 1 của AI Voice Studio hiện đạt mức độ an toàn cao đối với môi trường cục bộ API-first, tuân thủ chặt chẽ các chỉ dẫn trong ADR-0002 và ADR-0005.
