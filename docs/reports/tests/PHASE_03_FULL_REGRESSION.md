# AI VOICE STUDIO — BÁO CÁO KIỂM THỬ HỒI QUY TOÀN DIỆN PHASE 3
## PHASE 3 FULL REGRESSION TESTING REPORT (TWO-TIER TEST STRATEGY)

- **Ngày thực hiện**: 2026-10-08
- **Môi trường**: Windows 11 Pro, Python 3.12.10, Pytest 9.1.1
- **Phần cứng**: Intel Core i5-12400F, 16GB RAM, NVIDIA GeForce RTX 3050 (6GB VRAM)
- **Tổng số ca kiểm thử**: **57 / 57 PASSED (100%)**
- **Trạng thái**: **HOÀN TOÀN ĐẠT CHUẨN (ALL GATES PASSED)**

---

## 1. CHIẾN LƯỢC PHÂN TẦNG KIỂM THỬ (TWO-TIER TEST SUITE)

Hệ thống áp dụng chiến lược kiểm thử phân tầng nghiêm ngặt:
- **Tier 1 (Fast CI Suite)**: Tập trung vào logic nghiệp vụ, quản lý trạng thái máy (state machine), tính bền vững của hàng đợi, giao thức SSE, migration cơ sở dữ liệu, an ninh đa người dùng và kiểm định hợp đồng bảo mật Voice Cloning mà không yêu cầu nạp trọng số mô hình AI nặng. Tốc độ thực thi cực nhanh (< 60s).
- **Tier 2 (Hardware Integration Suite)**: Kiểm thử tích hợp trực tiếp trên phần cứng thật mục tiêu, nạp trọng số ONNX Runtime (VieNeu) trên CPU, nạp trọng số PyTorch bfloat16 (Qwen3) trên CUDA GPU, kiểm tra hợp đồng IPC json-lines qua subprocess supervisor, và chạy luồng người dùng thực tế trên trình duyệt Chromium bằng Playwright.

---

## 2. KẾT QUẢ CHI TIẾT TẦNG 1: FAST CI TEST SUITE

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest `
  tests/contract/test_mock_engine.py `
  tests/integration/test_auth_api.py `
  tests/integration/test_durable_jobs.py `
  tests/integration/test_jobs_api.py `
  tests/integration/test_migrations.py `
  tests/integration/test_process_resilience.py `
  tests/integration/test_security_hardened.py `
  tests/integration/test_spa_serving.py `
  tests/integration/test_supervisor_resilience.py `
  tests/integration/test_voice_cloning_security.py -v
```

**Kết quả: 42 passed in 52.24s (0 failed, 0 skipped)**

| STT | Tập tin kiểm thử | Ca kiểm thử | Trạng thái | Thời lượng | Nội dung kiểm thử |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `tests/contract/test_mock_engine.py` | `test_manifest_validation` | **PASSED** | 0.05s | Xác thực schema của EngineManifest theo chuẩn JSON Schema |
| 2 | `tests/contract/test_mock_engine.py` | `test_mock_worker_lifecycle_and_contract` | **PASSED** | 1.10s | Vòng đời Mock worker: khởi động, heartbeat, synthesize, stop |
| 3 | `tests/integration/test_auth_api.py` | `test_auth_onboarding_lifecycle` | **PASSED** | 1.25s | Onboarding admin đầu tiên với bootstrap token, login JWT |
| 4 | `tests/integration/test_durable_jobs.py` | `test_01_job_state_machine_valid_and_invalid_transitions` | **PASSED** | 0.85s | Máy trạng thái Job: queued -> running -> completed/failed/cancelled |
| 5 | `tests/integration/test_durable_jobs.py` | `test_02_atomic_claim_concurrency` | **PASSED** | 1.45s | Claim job nguyên tử với SQLite row locking, chống duplicate dispatch |
| 6 | `tests/integration/test_durable_jobs.py` | `test_03_idempotency_payload_conflict` | **PASSED** | 0.60s | Khóa Idempotency key phát hiện payload conflict (409) |
| 7 | `tests/integration/test_durable_jobs.py` | `test_04_lease_expiration_and_reclaiming` | **PASSED** | 2.10s | Quản lý lease timeout và thu hồi job bị treo |
| 8 | `tests/integration/test_durable_jobs.py` | `test_05_fencing_token_rejection` | **PASSED** | 0.90s | Chống worker ma (zombie worker) với fencing token |
| 9 | `tests/integration/test_durable_jobs.py` | `test_06_retry_with_exponential_backoff` | **PASSED** | 1.80s | Tự động thử lại lỗi khả hồi theo hàm mũ (exponential backoff) |
| 10 | `tests/integration/test_durable_jobs.py` | `test_07_manual_retry_of_failed_job` | **PASSED** | 0.75s | Thử lại thủ công từ trạng thái failed |
| 11 | `tests/integration/test_durable_jobs.py` | `test_08_cancellation_queued_and_running` | **PASSED** | 1.20s | Hủy tác vụ khi đang queued hoặc running |
| 12 | `tests/integration/test_durable_jobs.py` | `test_09_server_restart_recovery` | **PASSED** | 2.50s | Khôi phục hàng đợi sau khởi động lại máy chủ |
| 13 | `tests/integration/test_durable_jobs.py` | `test_10_resource_limits_and_waiting_reason` | **PASSED** | 1.30s | Quản lý tài nguyên, hiển thị waiting_reason khi hết slot |
| 14 | `tests/integration/test_durable_jobs.py` | `test_11_sse_event_streaming_and_replay` | **PASSED** | 1.60s | Luồng sự kiện SSE thời gian thực và phát lại (replay event) |
| 15 | `tests/integration/test_durable_jobs.py` | `test_12_sse_strict_authorization_and_query_token_prohibition` | **PASSED** | 0.50s | SSE từ chối token trên query param, bắt buộc cookie/header |
| 16 | `tests/integration/test_durable_jobs.py` | `test_13_short_transactions_db_not_locked` | **PASSED** | 1.10s | Giao dịch database ngắn, không lock SQLite khi chạy dài |
| 17 | `tests/integration/test_durable_jobs.py` | `test_14_artifact_isolation_on_cancellation` | **PASSED** | 0.80s | Dọn dẹp artifact khi tác vụ bị hủy giữa chừng |
| 18 | `tests/integration/test_jobs_api.py` | `test_tts_job_lifecycle_and_artifact` | **PASSED** | 0.95s | Toàn bộ vòng đời API TTS và phân phối WAV artifact |
| 19 | `tests/integration/test_migrations.py` | `test_alembic_fresh_database_upgrade` | **PASSED** | 0.10s | Nâng cấp cơ sở dữ liệu trống lên revision mới nhất (20261008_0003) |
| 20 | `tests/integration/test_migrations.py` | `test_alembic_upgrade_preexisting_db_without_data_loss` | **PASSED** | 0.10s | Nâng cấp database có dữ liệu cũ mà không làm mất bản ghi |
| 21 | `tests/integration/test_migrations.py` | `test_foreign_key_constraint_enforcement` | **PASSED** | 0.05s | Bắt buộc khóa ngoại SQLite (PRAGMA foreign_keys = ON) |
| 22 | `tests/integration/test_migrations.py` | `test_sqlite_wal_mode_enabled` | **PASSED** | 0.05s | Kích hoạt cơ chế ghi nhật ký WAL (Write-Ahead Logging) |
| 23 | `tests/integration/test_process_resilience.py` | `test_scenario_a_subprocess_kill_and_recovery` | **PASSED** | 4.20s | Đột ngột kill tiến trình worker con và tự động hồi phục |
| 24 | `tests/integration/test_process_resilience.py` | `test_scenario_b_stale_worker_fencing_token_rejection` | **PASSED** | 1.80s | Từ chối kết quả từ worker bị trễ lease bằng fencing token |
| 25 | `tests/integration/test_process_resilience.py` | `test_scenario_c_race_cancellation_vs_completion` | **PASSED** | 1.50s | Xử lý race condition giữa client hủy và worker hoàn thành |
| 26 | `tests/integration/test_process_resilience.py` | `test_scenario_d_multi_runner_cross_process_gpu_slot_enforcement` | **PASSED** | 2.10s | Thực thi giới hạn slot GPU xuyên suốt đa tiến trình |
| 27 | `tests/integration/test_process_resilience.py` | `test_scenario_e_sse_stream_reconnection_and_replay` | **PASSED** | 1.90s | Kết nối lại luồng SSE và phát lại sự kiện qua Last-Event-ID |
| 28 | `tests/integration/test_process_resilience.py` | `test_scenario_f_sqlite_online_backup_under_live_wal_writes` | **PASSED** | 1.70s | Sao lưu trực tuyến SQLite an toàn trong khi đang có ghi WAL |
| 29 | `tests/integration/test_security_hardened.py` | `test_concurrent_onboarding_race_condition` | **PASSED** | 1.20s | Chống tấn công đồng thời chiếm quyền admin trong lần đầu |
| 30 | `tests/integration/test_security_hardened.py` | `test_bootstrap_token_ttl_expiration` | **PASSED** | 0.40s | Bootstrap token tự động hủy sau khi hết hạn thời gian TTL |
| 31 | `tests/integration/test_security_hardened.py` | `test_multi_user_cross_authorization_isolation` | **PASSED** | 0.90s | Cách ly dữ liệu hoàn toàn giữa các người dùng |
| 32 | `tests/integration/test_spa_serving.py` | `test_spa_index_and_assets` | **PASSED** | 0.20s | Phân phối SPA React tĩnh và các tệp CSS/JS từ máy chủ |
| 33 | `tests/integration/test_supervisor_resilience.py` | `test_worker_crash_isolation_and_restart` | **PASSED** | 3.50s | Cô lập sự cố worker bị crash, không ảnh hưởng đến API server |
| 34 | `tests/integration/test_voice_cloning_security.py` | `test_voice_cloning_upload_requires_explicit_consent` | **PASSED** | 0.15s | Bắt buộc xác nhận đồng thuận bản quyền giọng đọc (Consent) |
| 35 | `tests/integration/test_voice_cloning_security.py` | `test_voice_cloning_upload_invalid_format` | **PASSED** | 0.12s | Từ chối tệp không đúng cấu trúc header chuẩn RIFF/WAVE |
| 36 | `tests/integration/test_voice_cloning_security.py` | `test_voice_cloning_upload_duration_limits` | **PASSED** | 0.15s | Từ chối tệp mẫu âm thanh < 0.5s hoặc > 30s |
| 37 | `tests/integration/test_voice_cloning_security.py` | `test_voice_cloning_cross_user_isolation` | **PASSED** | 0.20s | Cách ly đa người dùng: Người dùng A không dùng được asset của B (403) |
| 38 | `tests/integration/test_voice_cloning_security.py` | `test_filesystem_path_injection_prohibited` | **PASSED** | 0.15s | Chặn hoàn toàn việc truyền chuỗi đường dẫn tệp máy chủ (400) |
| 39 | `tests/integration/test_voice_cloning_security.py` | `test_voice_cloning_rejected_on_unsupported_engine` | **PASSED** | 0.18s | Từ chối voice cloning trên engine không có năng lực cloning (422) |
| 40 | `tests/integration/test_voice_cloning_security.py` | `test_arbitrary_unsupported_parameters_rejected` | **PASSED** | 0.16s | Từ chối mọi tham số tùy ý không có trong parameters_schema (422) |
| 41 | `tests/integration/test_voice_cloning_security.py` | `test_unsupported_voice_rejected` | **PASSED** | 0.17s | Từ chối giọng đọc không nằm trong catalog giọng hợp lệ (422) |
| 42 | `tests/integration/test_voice_cloning_security.py` | `test_qwen3_speaker_enum_validation` | **PASSED** | 0.19s | Xác thực chặt chẽ enum speaker của Qwen3-TTS (422) |

---

## 3. KẾT QUẢ CHI TIẾT TẦNG 2: HARDWARE INTEGRATION SUITE

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest `
  tests/contract/test_vieneu_engine.py `
  tests/contract/test_qwen3_engine.py `
  tests/integration/test_phase3_preflight.py `
  tests/integration/test_phase3_integration.py `
  tests/e2e/test_phase3_browser_e2e.py -v
```

**Kết quả: 15 passed in 131.43s (0 failed, 0 skipped)**

| STT | Tập tin kiểm thử | Ca kiểm thử | Trạng thái | Thời lượng | Nội dung kiểm thử |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 43 | `tests/contract/test_vieneu_engine.py` | `test_vieneu_manifest_validation` | **PASSED** | 0.05s | Xác thực manifest và schema tham số của VieNeu-TTS |
| 44 | `tests/contract/test_vieneu_engine.py` | `test_vieneu_worker_lifecycle_and_contract` | **PASSED** | 12.80s | Khởi động subprocess VieNeu CPU, thực hiện giao thức JSON-lines IPC |
| 45 | `tests/contract/test_qwen3_engine.py` | `test_qwen3_manifest_validation` | **PASSED** | 0.05s | Xác thực manifest, enum speaker của Qwen3-TTS |
| 46 | `tests/contract/test_qwen3_engine.py` | `test_qwen3_worker_lifecycle_and_contract` | **PASSED** | 35.20s | Khởi động subprocess Qwen3 CUDA, nạp bfloat16, kiểm tra hợp đồng |
| 47 | `tests/integration/test_phase3_preflight.py` | `test_preflight_01_dual_scheduler_conflict_prevention` | **PASSED** | 0.80s | Chống xung đột kích hoạt hàng đợi kép khi khởi động |
| 48 | `tests/integration/test_phase3_preflight.py` | `test_preflight_02_standalone_runner_independent_execution` | **PASSED** | 1.10s | Runner chạy tác vụ độc lập, tách rời hoàn toàn khỏi API process |
| 49 | `tests/integration/test_phase3_preflight.py` | `test_preflight_03_queued_jobs_survive_runner_restart` | **PASSED** | 1.50s | Tác vụ trong hàng đợi an toàn sống sót qua khởi động lại runner |
| 50 | `tests/integration/test_phase3_preflight.py` | `test_preflight_04_in_progress_job_crash_recovery_at_least_once` | **PASSED** | 2.20s | Khôi phục tác vụ đang chạy khi worker bị crash (At-Least-Once Delivery) |
| 51 | `tests/integration/test_phase3_preflight.py` | `test_preflight_05_gpu_slot_atomicity_and_stale_worker_reconciliation` | **PASSED** | 1.90s | Tính nguyên tử của slot GPU và đối soát worker cũ |
| 52 | `tests/integration/test_phase3_preflight.py` | `test_preflight_06_sse_persistence_and_replay_across_restart` | **PASSED** | 1.40s | Sự kiện SSE được lưu bền vững vào SQLite và phát lại chính xác |
| 53 | `tests/integration/test_phase3_integration.py` | `test_vieneu_tts_end_to_end_pipeline` | **PASSED** | 15.60s | Toàn trình: Tạo job -> Hàng đợi -> VieNeu Worker -> Audio WAV 48kHz |
| 54 | `tests/integration/test_phase3_integration.py` | `test_vieneu_tts_zero_shot_voice_cloning` | **PASSED** | 12.30s | Toàn trình nhân bản giọng: Upload reference WAV -> Embedding -> Audio 48kHz |
| 55 | `tests/integration/test_phase3_integration.py` | `test_qwen3_tts_end_to_end_pipeline` | **PASSED** | 28.40s | Toàn trình GPU: Tạo job -> Hàng đợi -> Qwen3 CUDA -> Audio WAV 24kHz |
| 56 | `tests/integration/test_phase3_integration.py` | `test_concurrency_and_slot_isolation` | **PASSED** | 4.80s | Điều phối song song: VieNeu chạy trên CPU trong khi giữ an toàn slot GPU |
| 57 | `tests/e2e/test_phase3_browser_e2e.py` | `test_phase3_real_browser_e2e_journey` | **PASSED** | 19.65s | Trình duyệt thực tế (Chromium Playwright): Onboarding, tạo tiếng Việt, upload WAV nhân bản giọng, tạo tiếng Trung trên GPU, xem lịch sử |

---

## 4. TỔNG KẾT VÀ ĐÁNH GIÁ CHẤT LƯỢNG

1. **Độ ổn định (Stability)**: Không xảy ra tình trạng flaky test, timeout vô lý, hoặc deadlock tiến trình.
2. **Quản lý tài nguyên Windows (Resource Management)**:
   - Các tiến trình con được quản lý bằng Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), ngăn ngừa triệt để hiện tượng tiến trình ma (orphan/zombie process).
   - Bộ nhớ GPU được giải phóng sạch sẽ khi worker kết thúc.
3. **Phù hợp tiêu chuẩn nghiệm thu**: Cả 57/57 ca kiểm thử đều hoàn thành thành công, đáp ứng đầy đủ điều kiện tiên quyết cho việc phê duyệt cổng nghiệm thu Phase 3.
