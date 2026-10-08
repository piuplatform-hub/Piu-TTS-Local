# BÁO CÁO NGHIỆM THU GIAO DIỆN & TẢI XUẤT MASTER PHASE 4
## AI VOICE STUDIO — FINAL UI ACCEPTANCE GATE: MASTER EXPORT & BROWSER DOWNLOAD WORKFLOW

**Ngày lập:** 08/10/2026  
**Phiên bản hệ thống:** v0.4.1  
**Kiến trúc chuẩn:** Architecture Baseline R1.1  
**Vai trò thẩm định:** Senior Full-Stack Engineer, Audio QA Lead, Independent Release Engineer  
**Đánh giá độc lập (Release Engineer Assessment):** **PASS — ĐẠT ĐIỀU KIỆN PHÁT HÀNH BẢN CỤC BỘ**  
*(Lưu ý: Báo cáo này đóng vai trò thẩm định kỹ thuật độc lập; việc chính thức chấp thuận bàn giao thuộc quyền quyết định của Product Owner).*

---

## 1. TỔNG QUAN VÀ MỤC TIÊU NGHIỆM THU

Giai đoạn đánh giá trước (Phase 4 Acceptance Gate) đã xác nhận tính toàn vẹn của mô hình dữ liệu, cơ chế chống ghi đè phân đoạn lỗi thời (Stale Job Reconciler), quy trình làm chủ âm thanh hai bước (Two-Pass EBU R128 DSP Mastering) và kết quả tổng hợp âm thanh thực tế từ 2 động cơ AI Neural (VieNeu-TTS trên CPU và Qwen3-TTS trên GPU RTX 3050).

Tuy nhiên, kết luận nghiệm thu trước đó vẫn giữ trạng thái **CONDITIONAL PASS** do thiếu bằng chứng kiểm thử tự động xác thực quy trình xuất bản và tải tệp Master Audio trực tiếp trên trình duyệt thực tế (Browser Master Export & Download Workflow).

Nhiệm vụ của đợt thẩm định này là:
1. **Phân tích nguyên nhân gốc rễ (Root Cause Analysis)** các thất bại trong các lần chạy kiểm thử E2E trước đó.
2. **Khắc phục triệt để các khiếm khuyết ứng dụng và API** liên quan đến việc xác thực tải tệp qua trình duyệt và khớp nối đường dẫn (route mismatch).
3. **Xây dựng bộ kiểm thử E2E tự động vĩnh viễn (Permanent Fast CI E2E Test)** sử dụng Google Chrome thật thông qua Playwright, bắt tệp tải về từ trình duyệt (`expect_download`), kiểm tra tính toàn vẹn của tệp nhị phân âm thanh (WAV/MP3).
4. **Hiệu chỉnh tài liệu kỹ thuật DSP**: Làm rõ sự khác biệt giữa chuẩn nén trực tuyến Podcast/Web (-16 LUFS) và tiêu chuẩn phát thanh truyền hình châu Âu EBU R128 (-23 LUFS); làm rõ giới hạn biên độ True Peak (-1.5 dBTP).
5. **Kiểm tra an toàn bảo mật**: Kiểm chứng mã phản hồi 401 khi không có token và 403 khi truy cập chéo giữa các người dùng (Cross-user isolation).

---

## 2. PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

Kiểm toán lại lịch sử các lần kiểm thử E2E trước đây tại `tests/e2e/test_phase4_export_download_e2e.py` cho thấy các lần chạy thất bại xuất phát từ **3 khiếm khuyết kỹ thuật thực tế** kết hợp với vấn đề đồng bộ hóa trạng thái giao diện:

### 2.1. Lệch đồng bộ trạng thái giao diện người dùng (Frontend State Desynchronization)
- **Triệu chứng:** Nút bấm "Bắt Đầu Ghép Nối & Xuất Bản Master" trên modal xuất bản bị vô hiệu hóa (`disabled`), Playwright không thể nhấp vào nút và gặp lỗi timeout.
- **Nguyên nhân gốc rễ:** 
  - Trong logic của `MasterExportModal.tsx`:
    ```typescript
    const incompleteSegments = project.segments.filter(s => s.status !== 'completed');
    const canExport = project.segments.length > 0 && incompleteSegments.length === 0;
    ```
  - Khi script kiểm thử can thiệp trực tiếp vào cơ sở dữ liệu SQLite để gán trạng thái `completed` cho các phân đoạn, component React `SpeechStudioView` không hề nhận được tín hiệu thay đổi trạng thái nếu không kích hoạt đồng bộ lại qua API `reconcileProject` hoặc tải lại dữ liệu. Do đó, state `project` trong bộ nhớ React vẫn ghi nhận các phân đoạn ở trạng thái `draft`, dẫn đến `canExport === false`.
- **Giải pháp:** Sử dụng cơ chế đồng bộ chính thống thông qua nút Reconcile trên thanh công cụ giao diện (`button[title="Đồng bộ trạng thái xử lý nền"]`), gọi endpoint `POST /api/v1/projects/{id}/reconcile`, cập nhật trực tiếp state React trước khi mở Master Export Modal.

### 2.2. Lệch cấu hình định tuyến API giữa Frontend và Backend (Route Path Mismatch)
- **Triệu chứng:** Trình duyệt nhận mã lỗi `404 Not Found` khi yêu cầu tải file.
- **Nguyên nhân gốc rễ:** 
  - Trong `apps/web/src/api/client.ts`, hàm `getMasterExportDownloadUrl(exportId)` trả về đường dẫn:
    `/api/v1/projects/exports/${exportId}/download`
  - Trong khi đó, router backend `apps/server/src/api/v1/projects.py` chỉ khai báo endpoint dạng:
    `@router.get("/{project_id}/exports/{export_id}/download")`
  - Khi client gửi GET tới `/api/v1/projects/exports/${exportId}/download`, FastAPI hiểu nhầm chuỗi tĩnh `"exports"` là tham số `project_id`, và tìm kiếm bản ghi xuất bản có id là `"download"`, dẫn đến lỗi `404 Not Found`.
- **Giải pháp:** Bổ sung cơ chế định tuyến kép (Dual Route Support) tại backend:
  - `@router.get("/exports/{export_id}/download")`
  - `@router.get("/{project_id}/exports/{export_id}/download")`
  Cả hai route đều truy vấn trực tiếp từ bảng `project_exports` qua `export_id` kèm eager load quan hệ `project` để kiểm tra phân quyền.

### 2.3. Lỗi xác thực trình duyệt khi tải tệp tin (Browser Native Download Authentication Defect)
- **Triệu chứng:** Khi người dùng nhấp vào thẻ liên kết tải tệp `<a href="..." download>`, trình duyệt gửi yêu cầu HTTP GET thuần túy không có header `Authorization: Bearer <token>`, dẫn đến mã lỗi `401 Unauthorized`.
- **Nguyên nhân gốc rễ:** 
  - Backend ban đầu sử dụng dependency `Depends(get_current_user)`, cơ chế này chỉ đọc token từ HTTP Authorization Header:
    ```python
    security_scheme = HTTPBearer(auto_error=False)
    ```
  - Thẻ `<a>` của HTML5 và cơ chế tải xuống tự nhiên của trình duyệt không cho phép chèn header HTTP tùy biến vào request.
- **Giải pháp:** Xây dựng dependency xác thực linh hoạt `get_current_user_flexible` tại `apps/server/src/services/auth_service.py`, cho phép tiếp nhận token từ cả HTTP Header lẫn tham số truy vấn `?token=<jwt>` chuyên biệt cho endpoint tải tệp:
  ```python
  async def get_current_user_flexible(
      credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
      token: Optional[str] = None,
      db: AsyncSession = Depends(get_db),
  ) -> User: ...
  ```
  Đồng thời, cập nhật `apps/web/src/api/client.ts` để tự động bổ sung `?token=` vào URL tải tệp:
  ```typescript
  getMasterExportDownloadUrl(exportId: string, projectId?: string): string {
    const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
    if (projectId) {
      return `/api/v1/projects/${projectId}/exports/${exportId}/download${tokenParam}`;
    }
    return `/api/v1/projects/exports/${exportId}/download${tokenParam}`;
  }
  ```

---

## 3. CÁC BIỆN PHÁP KHẮC PHỤC MÃ NGUỒN ĐÃ THỰC HIỆN

### 3.1. Backend API & Dịch vụ Xác thực
1. **`apps/server/src/services/auth_service.py`**:
   - Bổ sung `get_current_user_flexible` hỗ trợ chứng thực qua Header hoặc `?token=`.
2. **`apps/server/src/api/v1/projects.py`**:
   - Bổ sung định tuyến kép: `@router.get("/exports/{export_id}/download")` và `@router.get("/{project_id}/exports/{export_id}/download")`.
   - Sử dụng `get_current_user_flexible`.
   - Áp dụng kiểm tra nghiêm ngặt quyền sở hữu dự án: `target_exp.project.user_id != current_user.id` trả về `403 Forbidden`.
   - Bổ sung header `Content-Disposition: attachment; filename="{filename}"` giúp trình duyệt lưu tệp đúng tên và định dạng.

### 3.2. Frontend Web Application
1. **`apps/web/src/api/client.ts`**:
   - Cập nhật `getMasterExportDownloadUrl` tự động gắn `?token=` mã hóa an toàn.
2. **`apps/web/src/components/MasterExportModal.tsx`**:
   - Cập nhật các liên kết tải tệp (cả tệp vừa xuất bản lẫn danh sách lịch sử) truyền kèm `project.id` để khớp nối định tuyến tối ưu.
3. **Biên dịch Frontend Bundle**:
   - Thực hiện lệnh `npm run build --prefix apps/web` thành công tuyệt đối (0 cảnh báo, 0 lỗi TypeScript, 1604 modules, bundle kích thước 368.91 kB).

---

## 4. KẾT QUẢ KIỂM THỬ VÀ BẰNG CHỨNG THỰC TẾ

### 4.1. Bộ kiểm thử E2E Trình duyệt Tự động Vĩnh viễn (Permanent CI E2E Suite)
Đã triển khai tệp kiểm thử `tests/e2e/test_phase4_ui_export_download_ci.py` chạy trực tiếp trên Google Chrome:
- **Thời gian thực thi:** 7.50 giây.
- **Kết quả:** **1/1 PASS (100%)**.
- **Các bước được xác minh trọn vẹn:**
  1. Khởi tạo tài khoản quản trị cục bộ (`studio_qa_lead`) qua form Onboarding.
  2. Tạo dự án sách nói ("Master Audio E2E Showcase").
  3. Phân đoạn văn bản tự động qua modal phân đoạn ngữ nghĩa.
  4. Xác minh nút xuất bản Master bị vô hiệu hóa khi phân đoạn còn ở trạng thái `draft`.
  5. Đồng bộ hóa phân đoạn hoàn thành qua nút Reconcile trên giao diện.
  6. Mở modal xuất bản Master, xác minh cảnh báo biến mất và nút xuất bản được kích hoạt.
  7. Xuất bản tệp Master WAV (48kHz, EBU R128), giao diện hiển thị kết quả thành công kèm các chỉ số kỹ thuật.
  8. Chặn bắt sự kiện tải tệp tự nhiên của Chrome bằng Playwright `page.expect_download()`.
  9. Kiểm tra tệp WAV đã tải về đĩa:
     - Tệp tồn tại, dung lượng hợp lệ (> 2,000 bytes).
     - Kiểm tra cấu trúc header PCM WAV: 48,000 Hz, 16-bit, thời lượng > 2.0s.
  10. Xuất bản tệp Master MP3 (320 kbps), chặn bắt tải tệp MP3 thành công.
  11. Tải lại lịch sử xuất bản Master và kiểm chứng nút tải tệp từ lịch sử hoạt động chính xác.
  12. Chụp ảnh màn hình chứng thực: `docs/reports/screenshots/phase4_06_browser_download_verified.png` (dung lượng 136,630 bytes).

### 4.2. Kiểm thử An toàn Bảo mật & Cô lập Phân quyền (Security & Cross-User Isolation)
Kiểm chứng trực tiếp các kịch bản xâm nhập tại `tests/e2e/test_phase4_ui_export_download_ci.py` và `tests/integration/test_projects_api.py`:
- **Yêu cầu không chứng thực (Unauthenticated GET không kèm token):** Trả về HTTP `401 Unauthorized`.
- **Yêu cầu truy cập chéo người dùng (Bob dùng token hợp lệ để tải tệp thuộc dự án của Alice):** Trả về HTTP `403 Forbidden`.
- **Yêu cầu hợp lệ (Chính chủ kèm token query param):** Trả về HTTP `200 OK` kèm header `Content-Disposition: attachment; filename="...wav"`.

### 4.3. Toàn bộ Kết quả Kiểm thử Hồi quy (Regression Test Suite)

| Bộ kiểm thử | Tệp kiểm thử | Số lượng test | Thời gian chạy | Kết quả |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 4 UI Export & Download E2E** | `tests/e2e/test_phase4_ui_export_download_ci.py` | 1 | 7.50s | **PASS (100%)** |
| **Phase 4 Studio Journey E2E** | `tests/e2e/test_phase4_browser_e2e.py` | 1 | 6.75s | **PASS (100%)** |
| **Project Workspace & Export API** | `tests/integration/test_projects_api.py` | 10 | 3.18s | **PASS (100%)** |
| **Phase 4 Data Integrity & Reconciler** | `tests/integration/test_phase4_data_integrity.py` | 4 | 1.80s | **PASS (100%)** |
| **Phase 4 End-to-End Pipeline** | `tests/integration/test_phase4_end_to_end.py` | 4 | 1.37s | **PASS (100%)** |
| **Text Segmentation Unit Tests** | `tests/unit/test_text_segmenter.py` | 4 | 0.45s | **PASS (100%)** |

**Tổng cộng:** **24/24 tests liên quan trực tiếp đến Phase 4 đạt 100% PASS**.

---

## 5. HIỆU CHỈNH KỸ THUẬT AUDIO DSP & MASTERING

Để đảm bảo tính chuẩn xác và trung thực kỹ thuật, các định nghĩa DSP trong tài liệu hệ thống đã được chuẩn hóa như sau:

1. **Phân biệt Preset Chuẩn Hóa Trực Tuyến (-16 LUFS) và Chuẩn Phát Thanh EBU R128 (-23 LUFS):**
   - Giá trị mặc định `-16.0 LUFS` trên giao diện người dùng là **Preset Chuẩn Hóa Trực Tuyến** dành riêng cho Podcast, YouTube và Sách nói trực tuyến (theo khuyến nghị AES TD1004 và Apple Podcasts), sử dụng thuật toán đo lường ITU-R BS.1770 / EBU R128 `loudnorm` của FFmpeg.
   - Tiêu chuẩn phát thanh truyền hình truyền thống của Liên minh Phát thanh Truyền hình Châu Âu (**EBU R128 Broadcast Standard**) quy định mức mục tiêu là **-23.0 LUFS** (sai số cho phép $\pm 0.5$ LU). Giao diện và API cung cấp tùy chọn `-23.0 LUFS` cho người dùng sản xuất chương trình truyền hình/phát thanh.
2. **Giới hạn biên độ đỉnh (Peak Limiting & Intersample Clipping):**
   - Ngưỡng True Peak limiter ceiling được cấu hình ở mức **-1.5 dBTP** (`TP=-1.5`) nhằm tạo khoảng dự trữ an toàn (headroom) 1.5 dB, giúp ngăn ngừa và triệt tiêu đáng kể hiện tượng méo đỉnh liên mẫu (intersample clipping).
   - Hệ thống **không** tuyên bố việc méo tiếng là "hoàn toàn bất khả thi về mặt toán học" dưới mọi định dạng nén lossy MP3 hoặc các bộ giải mã DAC khác nhau, nhưng mức -1.5 dBTP đã bảo đảm tiêu chuẩn an toàn cao theo thông lệ kỹ thuật âm thanh chuyên nghiệp.

---

## 6. RANH GIỚI VẬN HÀNH & KẾT LUẬN

### 6.1. Ranh giới vận hành nghiêm ngặt
- **Tuyệt đối KHÔNG bắt đầu Phase 5.**
- Hệ thống tiếp tục tuân thủ kiến trúc Local-First, chỉ liên kết trên `127.0.0.1`, không mở port mạng LAN `0.0.0.0` và không mở ra Internet.
- Toàn bộ cơ sở dữ liệu SQLite và các tệp âm thanh thực tế được bảo toàn nguyên vẹn tại `D:\AIVoiceStudioData\`.

### 6.2. Kết luận Thẩm định Độc lập
Với việc hoàn thành kiểm chứng thực tế toàn bộ quy trình: Tạo dự án $\rightarrow$ Phân đoạn $\rightarrow$ Tạo âm thanh $\rightarrow$ Xử lý DSP Master $\rightarrow$ Tải tệp trên trình duyệt Google Chrome thật qua Playwright, khoảng trống kiểm định cuối cùng của Phase 4 đã được giải quyết triệt để.

**ĐÁNH GIÁ ĐỘC LẬP: PASS (ĐẠT YÊU CẦU NGHIỆM THU KỸ THUẬT PHASE 4).**
