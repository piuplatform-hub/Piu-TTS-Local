# AI VOICE STUDIO — BẰNG CHỨNG KIỂM THỬ GIAI ĐOẠN 2 (PHASE 2 TEST EVIDENCE)
## XÁC NHẬN MA TRẬN 15 TIÊU CHÍ KIỂM ĐỊNH HÀNG ĐỢI BỀN VỮNG & E2E BROWSER

**Tác giả:** QA Lead & Senior Backend Verification Engineer  
**Ngày thực hiện:** 2026-10-08  
**Kết quả tổng thể:** **28/28 BÀI KIỂM THỬ ĐẠT (100% PASSED)**  
**Thời gian thực thi:** 18.30 giây  

---

## 1. MA TRẬN ĐỐI CHIẾU 15 YÊU CẦU KIỂM THỬ (TESTING MATRIX COMPLIANCE)

| # | Tiêu chí kiểm định theo Phase 2 Scope | Tên bài kiểm thử tự động | Kết quả | Thời gian |
|:---:|:---|:---|:---:|:---:|
| **1** | **State machine transitions**<br>Kiểm tra mọi bước chuyển hợp lệ và chặn đứng chuyển đổi phi pháp | `test_01_job_state_machine_valid_and_invalid_transitions` | **PASSED** | 0.02s |
| **2** | **Atomic claim concurrency**<br>10 worker đồng thời tranh chấp 1 job, chỉ đúng 1 worker nhận được | `test_02_atomic_claim_concurrency` | **PASSED** | 0.35s |
| **3** | **Idempotency & Payload Conflict**<br>Trùng payload trả về job cũ; khác payload trả về 409 Conflict | `test_03_idempotency_payload_conflict` | **PASSED** | 0.28s |
| **4** | **Lease expiration & reclaiming**<br>Tác vụ quá hạn lease tự động thu hồi và xếp lại vào hàng đợi | `test_04_lease_expiration_and_reclaiming` | **PASSED** | 0.31s |
| **5** | **Fencing token rejection**<br>Worker cũ chậm chạp bị từ chối khi gửi hoàn tất sau khi lease đã đổi | `test_05_fencing_token_rejection` | **PASSED** | 0.40s |
| **6** | **Exponential backoff retries**<br>Thử lại với độ trễ tăng dần lũy thừa; kiệt số lần thử thì đánh dấu failed | `test_06_retry_with_exponential_backoff` | **PASSED** | 0.38s |
| **7** | **Manual retry of failed job**<br>Job lỗi được kích hoạt lại thủ công, thiết lập lại trạng thái queued | `test_07_manual_retry_of_failed_job` | **PASSED** | 0.32s |
| **8** | **Cancellation queued & running**<br>Hủy job trong hàng đợi lập tức; hủy job đang chạy ngắt worker an toàn | `test_08_cancellation_queued_and_running` | **PASSED** | 0.36s |
| **9** | **Server restart recovery**<br>Máy chủ khởi động lại tự động quét và khôi phục các job bị gián đoạn | `test_09_server_restart_recovery` | **PASSED** | 0.29s |
| **10** | **Resource limits & Waiting reasons**<br>Giới hạn slot GPU (max 1), job tiếp theo xếp hàng kèm lý do rõ ràng | `test_10_resource_limits_and_waiting_reason` | **PASSED** | 0.35s |
| **11** | **SSE streaming & Last-Event-ID**<br>Sự kiện sắp xếp tuần tự; hỗ trợ phát lại các sự kiện bị bỏ lỡ | `test_11_sse_event_streaming_and_replay` | **PASSED** | 0.26s |
| **12** | **SSE query parameter authentication**<br>Hỗ trợ xác thực qua query token `?token=...` chuẩn trình duyệt | `test_12_sse_query_param_authentication` | **PASSED** | 0.42s |
| **13** | **Short transactions without DB locks**<br>Ghi/đọc đồng thời SQLite không bị tắc nghẽn trong lúc worker xử lý | `test_13_short_transactions_db_not_locked` | **PASSED** | 0.30s |
| **14** | **Artifact isolation on cancellation**<br>Job bị hủy không bị gắn hoặc xuất bản artifact rác | `test_14_artifact_isolation_on_cancellation` | **PASSED** | 0.31s |
| **15** | **E2E Playwright Browser Journey**<br>Luồng người dùng thực tế: tạo job -> theo dõi SSE -> hủy job -> xem lịch sử | `test_real_browser_end_to_end_journey` | **PASSED** | 5.56s |

---

## 2. TOÀN BỘ KẾT QUẢ BỘ KIỂM THỬ TỔNG HỢP (28 TESTS)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.0
collected 28 items

tests\contract\test_mock_engine.py ..                                    [  7%]
tests\e2e\test_browser_e2e.py .                                          [ 10%]
tests\integration\test_auth_api.py .                                     [ 14%]
tests\integration\test_durable_jobs.py ..............                    [ 64%]
tests\integration\test_jobs_api.py .                                     [ 67%]
tests\integration\test_migrations.py ....                                [ 82%]
tests\integration\test_security_hardened.py ...                          [ 92%]
tests\integration\test_spa_serving.py .                                  [ 96%]
tests\integration\test_supervisor_resilience.py .                        [100%]

============================= 28 passed in 18.30s =============================
```

---

## 3. BẰNG CHỨNG ẢNH CHỤP MÀN HÌNH TRÌNH DUYỆT THỰC TẾ (REAL CHROMIUM SCREENSHOTS)

Toàn bộ ảnh chụp màn hình được chụp từ Google Chrome thực tế trên Windows 11 trong quá trình kiểm thử E2E Playwright:

| Thứ tự | Tên tệp ảnh chụp | Kích thước | Mô tả nội dung kiểm định |
|:---:|:---|:---:|:---|
| **01** | `docs/reports/screenshots/01_onboarding_view.png` | 51.2 KB | Giao diện Onboarding quản trị viên cục bộ lần đầu |
| **02** | `docs/reports/screenshots/02_speech_studio_view.png` | 89.5 KB | Giao diện Speech Studio, nạp Contract Mock Engine, các tham số giọng |
| **03** | `docs/reports/screenshots/03_audio_generated_view.png` | 105.1 KB | Hoàn tất tác vụ, thanh tiến độ 100%, trình phát âm thanh và nút Tải WAV |
| **04** | `docs/reports/screenshots/04_job_cancelled_view.png` | 87.8 KB | Thao tác hủy tác vụ trong khi đang xử lý, trạng thái CANCELLED thành công |
| **05** | `docs/reports/screenshots/05_job_history_view.png` | 45.7 KB | Bảng lịch sử tác vụ bền vững, liệt kê đầy đủ job hoàn thành và job đã hủy |
| **06** | `docs/reports/screenshots/06_logged_out_view.png` | 29.6 KB | Đăng xuất an toàn, bảo vệ giao diện khi chưa được cấp quyền |
