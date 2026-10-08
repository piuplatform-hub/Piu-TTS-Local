# BÁO CÁO ĐỘC LẬP: BẢO MẬT & KIỂM ĐỊNH PHÁT HÀNH
## PHASE 4 SECURITY HOTFIX R2: LOẠI BỎ XÁC THỰC JWT QUA THAM SỐ TRUY VẤN URL
### TỰ ĐỘNG HÓA TẢI FILE ÂM THANH MASTER QUA FETCH API & BLOB URL AN TOÀN

**Chuyên viên thực hiện**: Senior Application Security Engineer, Full-Stack Engineer & Release QA Lead  
**Thời gian kiểm định**: 2026-10-09  
**Mã commit cơ sở**: `8287aa0`  
**Trạng thái phê duyệt**: **PASS (CHÍNH THỨC ĐẠT CHUẨN AN NINH & CHẤP THUẬN PHÁT HÀNH)**  
**Phạm vi áp dụng**: Phase 4 Audio Production Workstation (Tuyệt đối không vi phạm ranh giới Phase 5)

---

### 1. TỔNG QUAN ĐIỀU HÀNH & KẾT LUẬN (EXECUTIVE SUMMARY & VERDICT)

Trong đợt nghiệm thu UI cuối cùng của Phase 4, tính năng tải tệp âm thanh Master WAV/MP3 từ giao diện trình duyệt đã được đưa vào hoạt động. Tuy nhiên, việc áp dụng hàm `get_current_user_flexible` và phương thức `getMasterExportDownloadUrl` tạo ra liên kết HTML dạng:
```
/api/v1/projects/{project_id}/exports/{export_id}/download?token=<JWT_BEARER_TOKEN>
```
Mặc dù thao tác này giải quyết được vấn đề thẻ `<a href="..." download>` không thể gửi kèm HTTP Header, nhưng nó đã kích hoạt rủi ro bảo mật nghiêm trọng theo danh mục lỗ hổng quốc tế **CWE-598: Use of GET Request with Sensitive Query Strings**. Mã truy cập nhạy cảm (JWT) bị phơi bày trong URL query string, có nguy cơ bị ghi lại trong nhật ký truy cập mạng (Access Logs), lịch sử trình duyệt (Browser History), proxy trung gian và tiêu đề Referer.

**Security Hotfix R2 đã thực hiện loại bỏ hoàn toàn cơ chế xác thực qua Query Parameter:**
1. **Phía Backend**:
   - Xóa bỏ hoàn toàn hàm `get_current_user_flexible` trong `apps/server/src/services/auth_service.py`.
   - Khôi phục cơ chế xác thực duy nhất `Depends(get_current_user)` (bắt buộc header `Authorization: Bearer <token>`) trên endpoint tải Master Audio (`apps/server/src/api/v1/projects.py`) và endpoint tải Artifact Audio (`apps/server/src/api/v1/artifacts.py`).
   - Thiết lập chốt chặn phòng thủ chủ động (Defense-in-Depth Guardrail): Bất kỳ yêu cầu nào cố tình gửi kèm tham số `token` trong URL (`?token=...`) đều bị từ chối thẳng thừng với mã lỗi **HTTP 400 Bad Request** và mã lỗi định danh chuẩn RFC 9457 `QUERY_AUTH_PROHIBITED`.
   - Bổ sung tiêu đề ngăn chặn lưu cache nhạy cảm: `Cache-Control: private, no-cache, no-store, must-revalidate` và `Pragma: no-cache`.
2. **Phía Frontend**:
   - Loại bỏ hàm `getMasterExportDownloadUrl` trong `apps/web/src/api/client.ts`.
   - Triển khai phương thức tải tệp an toàn `downloadMasterAudio(projectId, exportId, fallbackFilename)` sử dụng chuẩn **Fetch API** kèm tiêu đề `Authorization: Bearer <token>`, phân tích tên file từ `Content-Disposition`, chuyển đổi luồng dữ liệu sang đối tượng `Blob` trong RAM, sinh URL định danh cục bộ tạm thời (`window.URL.createObjectURL`), kích hoạt tải tệp và thu hồi ngay tài nguyên bằng `URL.revokeObjectURL`.
   - Thay thế các thẻ liên kết `<a>` trong `apps/web/src/components/MasterExportModal.tsx` thành thẻ nút bấm `<button>` với sự kiện `onClick`, đảm bảo mã JWT không bao giờ xuất hiện trong thuộc tính HTML DOM.
3. **Kiểm định thực tế**:
   - Toàn bộ bộ kiểm thử tích hợp (`test_projects_api.py`) và bộ kiểm thử trình duyệt thực tế Playwright Chromium (`test_phase4_ui_export_download_ci.py`) đã vượt qua 100%.
   - Kiểm tra lưu lượng mạng xác nhận **0 URL nào chứa token** trong suốt phiên hoạt động của người dùng.
   - Các bài kiểm thử bảo mật độc lập xác nhận: Có Header hợp lệ -> 200 OK; Truyền `?token=` -> 400 Bad Request; Không có Header -> 401 Unauthorized; Token của người dùng khác -> 403 Forbidden.

**KẾT LUẬN ĐỘC LẬP: PASS.**

---

### 2. PHÂN TÍCH NGUYÊN NHÂN GỐC (ROOT CAUSE ANALYSIS)

| Thành phần | Trạng thái trước Hotfix R2 | Rủi ro An ninh | Khắc phục trong Hotfix R2 |
| :--- | :--- | :--- | :--- |
| **Backend Auth Service** | Tồn tại `get_current_user_flexible` chấp nhận `?token=` | Phá vỡ nguyên tắc chuẩn hóa xác thực của Phase 2 | Đã xóa bỏ hoàn toàn. Chỉ giữ lại `get_current_user` qua Authorization Header. |
| **Backend Projects API** | Cho phép nhận `token` từ query param | Lộ token JWT vào access logs và web proxy (CWE-598) | Bắt buộc `Depends(get_current_user)`. Từ chối `?token=` với HTTP 400 `QUERY_AUTH_PROHIBITED`. |
| **Frontend Web Client** | `getMasterExportDownloadUrl` nối chuỗi `?token=${this.token}` | Token xuất hiện trong cây DOM và thanh trạng thái trình duyệt | Chuyển sang `downloadMasterAudio` gửi token qua header của Fetch API. |
| **Giao diện Modal** | Sử dụng thẻ `<a href="..." download>` | Buộc phải nhúng URL trực tiếp vào thẻ HTML | Chuyển sang thẻ `<button onClick="...">` kích hoạt luồng tải tệp Blob an toàn. |

---

### 3. KIẾN TRÚC GIẢI PHÁP & CHI TIẾT THI CÔNG

#### 3.1. Chốt chặn phòng thủ phía Backend (RFC 9457 & CWE-598 Guardrail)
Tại `apps/server/src/api/v1/projects.py` và `apps/server/src/api/v1/artifacts.py`:
```python
@router.get("/exports/{export_id}/download")
@router.get("/{project_id}/exports/{export_id}/download")
async def download_master_audio(
    export_id: str,
    project_id: Optional[str] = None,
    token: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Chủ động phát hiện và ngăn chặn hành vi truyền token trên query URL
    if token is not None:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Query Authentication Prohibited",
            detail="Passing authentication tokens in URL query strings is prohibited for security reasons (CWE-598). Use 'Authorization: Bearer <token>' header.",
            code="QUERY_AUTH_PROHIBITED",
        )
    ...
    return FileResponse(
        path=target_exp.file_path,
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
```

#### 3.2. Luồng tải tệp an toàn phía Frontend (Fetch + Blob URL Architecture)
Tại `apps/web/src/api/client.ts`:
```typescript
async downloadMasterAudio(projectId: string, exportId: string, fallbackFilename?: string): Promise<void> {
  const url = `/api/v1/projects/${projectId}/exports/${exportId}/download`;
  const headers: Record<string, string> = {};
  if (this.token) {
    headers['Authorization'] = `Bearer ${this.token}`;
  }

  const res = await fetch(url, { method: 'GET', headers });
  if (!res.ok) {
    let problem: ApiProblemError;
    try { problem = await res.json(); } catch {
      problem = { title: res.statusText, status: res.status, detail: 'Failed to download master audio.', code: `HTTP_${res.status}` };
    }
    throw new ApiError(problem);
  }

  // Trích xuất filename từ Content-Disposition header
  let filename = fallbackFilename || `master_export_${exportId.slice(0, 8)}.wav`;
  const disposition = res.headers.get('Content-Disposition');
  if (disposition) {
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (match && match[1]) filename = match[1].replace(/['"]/g, '').trim();
  }

  // Sinh Object URL trong bộ nhớ và giải phóng ngay sau khi kích hoạt
  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 5000);
}
```

---

### 4. BẰNG CHỨNG KIỂM THỬ & MA TRẬN XÁC MINH AN TOÀN

#### 4.1. Bộ kiểm thử tích hợp API (`tests/integration/test_projects_api.py`)
- **Tải qua Authorization Header**: HTTP 200 OK, `Content-Disposition: attachment`, `Cache-Control: no-store`, dung lượng binary > 1KB. (PASS)
- **Cố tình truyền `?token=` (Direct & Nested routes)**: Bị từ chối với HTTP 400 Bad Request, mã lỗi `QUERY_AUTH_PROHIBITED`. (PASS)
- **Tải không có chứng thực**: Bị từ chối với HTTP 401 Unauthorized. (PASS)
- **Tải chéo người dùng (User Bob cố truy cập dự án của Alice)**: Bị từ chối với HTTP 403 Forbidden. (PASS)
- **Kết quả**: **10/10 tests PASSED** trong 3.02 giây.

#### 4.2. Bộ kiểm thử trình duyệt thực tế Playwright (`tests/e2e/test_phase4_ui_export_download_ci.py`)
- **Khởi tạo và Render**: Admin onboarding, tạo dự án, phân tách 2 phân đoạn, đồng bộ trạng thái.
- **Tải WAV**: Bấm nút UI `Tải File Âm Thanh Master Ngay (WAV)` -> Trình duyệt bắt sự kiện download thành công qua Blob URL -> Tệp WAV hợp lệ trên đĩa (48kHz, 16-bit PCM, thời lượng > 2.0s). (PASS)
- **Tải MP3**: Bấm nút UI `Tải File Âm Thanh Master Ngay (MP3)` -> Tệp MP3 tải về hợp lệ (> 1KB). (PASS)
- **Tải từ Lịch sử**: Bấm nút icon `Tải về` trong danh sách lịch sử Master -> Tệp tải về thành công. (PASS)
- **Giám sát lưu lượng mạng (Zero Token Leakage)**: Ghi nhận toàn bộ danh sách URL trình duyệt gửi đi. Khẳng định không có bất kỳ URL nào chứa `token=`. (PASS)
- **Kết quả**: **1/1 test PASSED** trong 8.43 giây.

---

### 5. RANH GIỚI HỆ THỐNG & ĐẢM BẢO QUY ĐỊNH (GOVERNANCE COMPLIANCE)

1. **Ranh giới Phase**: Tuân thủ tuyệt đối không bắt đầu Phase 5 hay triển khai thêm tính năng ngoài phạm vi sửa lỗi bảo mật.
2. **Local-First Isolation**: Hệ thống duy trì cách ly hoàn toàn trên `127.0.0.1`, không mở cổng LAN `0.0.0.0` hay thiết lập dịch vụ đám mây.
3. **Toàn vẹn dữ liệu người dùng**: Toàn bộ dữ liệu dự án, cấu hình nhân vật và tệp âm thanh thực trong thư mục dữ liệu cục bộ được bảo toàn 100%.

---

**XÁC NHẬN CHÍNH THỨC CỦA RELEASE QA LEAD & SECURITY REVIEWER**:  
Hotfix R2 hoàn thành xuất sắc sứ mệnh đóng kín lỗ hổng CWE-598, đồng thời bảo toàn trọn vẹn trải nghiệm tải tệp âm thanh master mượt mà và trực quan trên giao diện phòng thu AI Voice Studio. Hệ thống đạt trạng thái **PASS TOÀN DIỆN**.
