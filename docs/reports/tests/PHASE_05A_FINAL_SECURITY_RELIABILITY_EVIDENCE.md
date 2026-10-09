# AI Voice Studio — Bằng Chứng Kiểm Thử Bảo Mật & Độ Tin Cậy Phase 5A Final Closure R2

**Ngày kiểm thử:** 09/10/2026  
**Môi trường:** Local Workstation (`127.0.0.1`), Windows 11, SQLite WAL Mode  
**Tình trạng:** 100% PASS  

---

## 1. BẰNG CHỨNG KIỂM THỬ ĐIỀU TIẾT ĐĂNG NHẬP (SECURITY SUITE)

**Lệnh thực thi:**
```powershell
.venv\Scripts\pytest.exe tests/integration/test_phase5a_final_r2_security.py -v
```

**Kết quả chi tiết:**
```text
tests/integration/test_phase5a_final_r2_security.py::test_distributed_brute_force_one_account_10_ips PASSED [ 14%]
tests/integration/test_phase5a_final_r2_security.py::test_credential_spraying_one_ip_20_usernames PASSED [ 28%]
tests/integration/test_phase5a_final_r2_security.py::test_two_legitimate_accounts_behind_shared_ip_no_collateral_lockout PASSED [ 42%]
tests/integration/test_phase5a_final_r2_security.py::test_concurrent_login_attempts_separate_sessions PASSED [ 57%]
tests/integration/test_phase5a_final_r2_security.py::test_rate_limit_expiry_and_success_reset PASSED [ 71%]
tests/integration/test_phase5a_final_r2_security.py::test_client_ip_spoof_resistance_ignores_x_forwarded_for PASSED [ 85%]
tests/integration/test_phase5a_final_r2_security.py::test_account_enumeration_resistance_uniform_responses PASSED [100%]

============================== 7 passed in 1.80s ==============================
```

**Bảo đảm an ninh đã xác thực:**
- Tấn công dò mật khẩu phân tán trên 10 IP khác nhau đối với một tài khoản bị khóa toàn diện ở lần thứ 11.
- Tấn công rải mật khẩu từ 1 IP nguồn trên 20 tài khoản khác nhau kích hoạt khóa IP nguồn ở lần thứ 21.
- Hai tài khoản hợp lệ cùng chung 1 IP không bị khóa oan khi mỗi người gõ sai 3 lần (< 5).
- 10 phiên database ghi nhận đăng nhập thất bại song song không gây deadlock trên SQLite.
- Gõ đúng mật khẩu lập tức giải tỏa trạng thái khóa tạm thời.
- Header `X-Forwarded-For` bị hoàn toàn phớt lờ; kẻ tấn công không thể đổi header để né rate limit.
- Phản hồi HTTP 401 đồng nhất ngăn chặn việc dò tìm tài khoản tồn tại (Enumeration Resistance).

---

## 2. BẰNG CHỨNG KIỂM THỬ VÒNG ĐỜI HẠN NGẠCH NGUYÊN TỬ (QUOTA LIFECYCLE SUITE)

**Lệnh thực thi:**
```powershell
.venv\Scripts\pytest.exe tests/integration/test_phase5a_final_r2_quota_lifecycle.py -v
```

**Kết quả chi tiết:**
```text
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_a_healthy_job_outlasts_original_reservation_ttl PASSED [ 16%]
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_b_worker_crashes_abandoned_reservation_cleaned_up PASSED [ 33%]
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_c_stale_worker_cannot_commit_reclaimed_reservation PASSED [ 50%]
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_d_concurrent_claims_compete_for_limited_quota PASSED [ 66%]
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_e_actual_output_size_exceeds_original_estimate PASSED [ 83%]
tests/integration/test_phase5a_final_r2_quota_lifecycle.py::test_scenario_f_export_fails_after_partial_temporary_file_cleanly_unlinked PASSED [100%]

============================== 6 passed in 0.93s ==============================
```

**Bảo đảm vòng đời đã xác thực:**
- Worker gửi heartbeat định kỳ gia hạn thời gian sống của hạn ngạch đặt trước (`renew_job_reservation`).
- Worker gặp sự cố bỏ rơi tác vụ, tiến trình dọn dẹp định kỳ thu hồi hạn ngạch mồ côi thành `EXPIRED`.
- Worker trễ hạn cố nộp tác vụ bị từ chối với `HTTP 409 Conflict` (`RESERVATION_STALE_OR_RECLAIMED`).
- Hai luồng ghi đồng thời tranh chấp hạn ngạch được kiểm soát chính xác, chỉ 1 luồng thành công.
- Kích thước âm thanh thực tế vượt ước tính ban đầu được điều chỉnh và tính toán chính xác vào tổng dung lượng.
- Quá trình Export gặp sự cố giải phóng reservation và tự động dọn sạch các tệp tạm (`unlink`).

---

## 3. BẰNG CHỨNG KIỂM THỬ ĐỘ ƯU TIÊN VÀ BỎ ĐÓI (PRIORITY FAIRNESS SUITE)

**Lệnh thực thi:**
```powershell
.venv\Scripts\pytest.exe tests/integration/test_phase5a_final_r2_priority_fairness.py -v
```

**Kết quả chi tiết:**
```text
tests/integration/test_phase5a_final_r2_priority_fairness.py::test_fairness_within_same_priority_tier PASSED [ 33%]
tests/integration/test_phase5a_final_r2_priority_fairness.py::test_priority_precedence_across_different_priorities PASSED [ 66%]
tests/integration/test_phase5a_final_r2_priority_fairness.py::test_starvation_risk_under_continuously_arriving_high_priority_jobs PASSED [100%]

============================== 3 passed in 8.15s ==============================
```

**Bảo đảm điều phối đã xác thực:**
- Luân phiên công bằng Round-Robin giữa Người dùng A và Người dùng B có cùng mức ưu tiên (`dispatch_order` xen kẽ A - B - A - B).
- Tác vụ độ ưu tiên 10 lập tức nhảy cóc vượt lên trước 10 tác vụ độ ưu tiên 1 đã xếp hàng từ trước.
- Khi luồng tác vụ ưu tiên 10 nộp liên tục, tác vụ ưu tiên 1 chấp nhận chờ đợi (xác nhận bản chất của mô hình Head-of-Line Priority không dùng Priority Aging).

---

## 4. BẰNG CHỨNG KIỂM THỬ BATCH DÀI TẬP TỰ TRỊ (AUTONOMOUS BATCH SUITE)

**Lệnh thực thi:**
```powershell
.venv\Scripts\pytest.exe tests/integration/test_phase5a_final_r2_autonomous_batch.py -v -s
```

**Kết quả chi tiết:**
```text
tests/integration/test_phase5a_final_r2_autonomous_batch.py::test_autonomous_progressive_batch_100_segments_no_browser_polling PASSED

====================== 1 passed, 202 warnings in 48.96s =======================
```

**Đặc điểm kiểm chứng:**
1. Tạo dự án 100 phân đoạn kịch bản ngắn.
2. Nộp toàn bộ: 25 phân đoạn đầu tiên chuyển sang `queued`, 75 phân đoạn chuyển sang `pending`.
3. Hoàn toàn không gọi API thăm dò từ phía máy khách (`GET /projects`).
4. Standalone Runner Daemon tự động nạp lũy tiến từng nhóm 25 tác vụ khi có slot trống.
5. Tại mốc 35 tác vụ: Mô phỏng tắt và kết nối lại pool kết nối DB của tiến trình API.
6. Tại mốc 70 tác vụ: Mô phỏng dừng và khởi động lại tiến trình Runner Daemon.
7. Toàn bộ 100/100 phân đoạn hoàn thành (`completed`), 0 phân đoạn tồn đọng (`pending = 0`), và 100 audio artifact độc bản được tạo lập (`len(set(artifacts)) == 100`).

---

## 5. BẰNG CHỨNG SAO LƯU TRỰC TUYẾN SQLITE (CLI BACKUP OUTPUT)

```powershell
.venv\Scripts\python.exe -m apps.server.src.backup create
```
```text
============================================================
 [AI VOICE STUDIO] ONLINE BACKUP CREATED SUCCESSFULLY
============================================================
 Source:      D:\AIVoiceStudioData\studio.db
 Destination: D:\AIVoiceStudioData\backups\studio_20261009_021229.db
 Size:        417,792 bytes
 SHA256:      d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527
 Integrity:   ok (Quick check: ok)
 Alembic Rev: 20261009_0006
 Tables:      {
  "users": 14,
  "engines": 3,
  "artifacts": 36,
  "jobs": 38,
  "alembic_version": 1,
  "job_events": 290,
  "reference_assets": 0,
  "projects": 9,
  "characters": 2,
  "script_segments": 32,
  "segment_revisions": 4,
  "project_exports": 8,
  "login_attempts": 48,
  "user_scheduling_states": 0,
  "storage_reservations": 3
}
============================================================
```

```powershell
.venv\Scripts\python.exe -m apps.server.src.backup verify D:\AIVoiceStudioData\backups\studio_20261009_021229.db
```
```text
============================================================
 [AI VOICE STUDIO] BACKUP VERIFICATION REPORT
============================================================
 Path:        D:\AIVoiceStudioData\backups\studio_20261009_021229.db
 Valid:       True
 Size:        417,792 bytes
 SHA256:      d440ec52bbb731b417d936f42f5b21434598d453d57f5fd5e8d280d2c0a56527
 Integrity:   ok
 Quick check: ok
 Alembic Rev: 20261009_0006
 Tables & Row Counts:
   - users               : 14 rows
   - engines             : 3 rows
   - artifacts           : 36 rows
   - jobs                : 38 rows
   - alembic_version     : 1 rows
   - job_events          : 290 rows
   - reference_assets    : 0 rows
   - projects            : 9 rows
   - characters          : 2 rows
   - script_segments     : 32 rows
   - segment_revisions   : 4 rows
   - project_exports     : 8 rows
   - login_attempts      : 48 rows
   - user_scheduling_states: 0 rows
   - storage_reservations: 3 rows
============================================================
```

---

## 6. BẰNG CHỨNG TOÀN DIỆN HỆ THỐNG

- **Tổng số Unit & Integration tests:** `102 passed in 275.38s`
- **Playwright Browser E2E tests:** `4 passed`
- **Frontend Build (`npm run build`):** `✓ built in 20.35s` (0 TypeScript errors)
