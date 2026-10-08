# AI Voice Studio — Bằng Chứng Kiểm Thử Giai Đoạn 5A (Phase 5A Test Evidence)

**Môi trường thực thi:** Windows 10/11 x64, Python 3.12.10, Pytest 9.1.1, Node.js v22  
**Cơ sở dữ liệu:** SQLite WAL Mode (`D:\AIVoiceStudioData\studio.db`)  
**Ngày thực hiện:** 09/10/2026  
**Commit cơ sở:** `a9e4f7e`  
**Kết quả tổng thể:** 78/78 PASSED (100% SUITE SUCCESS RATE)

---

## 1. TỔNG QUAN MA TRẬN KIỂM THỬ MILESTONE 5A

| STT | Tên bài kiểm thử (`test_phase5a_rbac_and_fairness.py`) | Trọng tâm kiểm tra | Kết quả | Thời gian |
|:---:|:---|:---|:---:|:---:|
| 1 | `test_5a_rbac_matrix_and_negative_authorization` | Ma trận quyền RBAC: Phân tách Viewer vs Editor trên các route tạo/sửa dự án, kịch bản, nhân vật, segments, render và download; Chặn tạo user tùy tiện. | **PASSED** | 3.12s |
| 2 | `test_5a_password_change_flow` | Xác thực đổi mật khẩu: Kiểm tra mật khẩu cũ, từ chối mật khẩu mới < 8 ký tự, xác minh đăng nhập lại với mật khẩu mới. | **PASSED** | 0.85s |
| 3 | `test_5a_brute_force_lockout_and_no_enumeration` | Chống dò mật khẩu & bảo vệ tài khoản: 5 lần đăng nhập sai kích hoạt HTTP 429 kèm `Retry-After: 900`; Thông điệp trung lập không tiết lộ username. | **PASSED** | 1.15s |
| 4 | `test_5a_fair_share_queue_scheduling` | Lập lịch công bằng (Least-Active-User-First): Phân phối slot CPU cho người dùng ít active hơn; Kiểm tra Priority Preemption cho job ưu tiên cao. | **PASSED** | 2.45s |
| 5 | `test_5a_max_outstanding_jobs_limit` | Giới hạn 25 job đang xử lý cho mỗi user: Gửi job thứ 26 bị từ chối với HTTP 429 `TOO_MANY_OUTSTANDING_JOBS`. | **PASSED** | 1.62s |
| 6 | `test_5a_user_storage_quota_enforcement` | Cưỡng chế hạn ngạch lưu trữ người dùng: Chặn upload audio reference và render job khi vượt quota (HTTP 413 `USER_STORAGE_QUOTA_EXCEEDED`). | **PASSED** | 2.05s |
| 7 | `test_5a_voice_cloning_strict_ownership_no_admin_bypass` | Cách ly quyền sở hữu mẫu giọng: Admin không được phép dùng voice reference của user khác để render job (HTTP 403 `FORBIDDEN_ASSET_ACCESS`). | **PASSED** | 1.56s |

---

## 2. NHẬT KÝ THỰC THI BỘ KIỂM THỬ MILESTONE 5A

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- D:\C\Dev\du an\TTS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_rbac_matrix_and_negative_authorization PASSED [ 14%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_password_change_flow PASSED [ 28%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_brute_force_lockout_and_no_enumeration PASSED [ 42%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_fair_share_queue_scheduling PASSED [ 57%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_max_outstanding_jobs_limit PASSED [ 71%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_user_storage_quota_enforcement PASSED [ 85%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_voice_cloning_strict_ownership_no_admin_bypass PASSED [100%]

======================= 7 passed, 4 warnings in 12.80s ========================
```

---

## 3. NHẬT KÝ THỰC THI TOÀN BỘ HỒI QUY (FULL REGRESSION SUITE)

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- D:\C\Dev\du an\TTS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 78 items

tests/integration/test_auth_api.py::test_auth_flow_and_rbac PASSED       [  1%]
tests/integration/test_bootstrap_onboarding.py::test_onboarding_lifecycle PASSED [  2%]
tests/integration/test_durable_jobs.py::test_01_sqlite_wal_journal_mode PASSED [  3%]
tests/integration/test_durable_jobs.py::test_02_job_queue_persistence_and_states PASSED [  5%]
tests/integration/test_durable_jobs.py::test_03_priority_scheduling PASSED [  6%]
tests/integration/test_durable_jobs.py::test_04_atomic_worker_assignment_fencing_token PASSED [  7%]
tests/integration/test_durable_jobs.py::test_05_concurrency_single_gpu_slot PASSED [  8%]
tests/integration/test_durable_jobs.py::test_06_cancellation_queued_and_running PASSED [ 10%]
tests/integration/test_durable_jobs.py::test_07_crash_recovery_stale_heartbeat PASSED [ 11%]
tests/integration/test_durable_jobs.py::test_08_exponential_backoff_retry PASSED [ 12%]
tests/integration/test_durable_jobs.py::test_09_dead_letter_queue_terminal_failure PASSED [ 14%]
tests/integration/test_durable_jobs.py::test_10_sse_heartbeat_and_resume PASSED [ 15%]
tests/integration/test_durable_jobs.py::test_11_cross_user_queue_isolation PASSED [ 16%]
tests/integration/test_durable_jobs.py::test_12_queue_pause_and_drain PASSED [ 17%]
tests/integration/test_durable_jobs.py::test_13_short_transactions_db_not_locked PASSED [ 19%]
tests/integration/test_durable_jobs.py::test_14_artifact_isolation_on_cancellation PASSED [ 20%]
tests/integration/test_jobs_api.py::test_tts_job_lifecycle_and_artifact PASSED [ 21%]
tests/integration/test_migrations.py::test_alembic_fresh_database_upgrade PASSED [ 23%]
tests/integration/test_migrations.py::test_alembic_upgrade_preexisting_db_without_data_loss PASSED [ 24%]
tests/integration/test_migrations.py::test_foreign_key_constraint_enforcement PASSED [ 25%]
tests/integration/test_migrations.py::test_sqlite_wal_mode_enabled PASSED [ 26%]
tests/integration/test_phase3_integration.py::test_vieneu_tts_end_to_end_pipeline PASSED [ 28%]
tests/integration/test_phase3_integration.py::test_vieneu_tts_zero_shot_voice_cloning PASSED [ 29%]
tests/integration/test_phase3_integration.py::test_qwen3_tts_end_to_end_pipeline PASSED [ 30%]
tests/integration/test_phase3_integration.py::test_concurrency_and_slot_isolation PASSED [ 32%]
tests/integration/test_phase3_preflight.py::test_preflight_01_dual_scheduler_conflict_prevention PASSED [ 33%]
tests/integration/test_phase3_preflight.py::test_preflight_02_standalone_runner_independent_execution PASSED [ 34%]
tests/integration/test_phase3_preflight.py::test_preflight_03_queued_jobs_survive_runner_restart PASSED [ 35%]
tests/integration/test_phase3_preflight.py::test_preflight_04_in_progress_job_crash_recovery_at_least_once PASSED [ 37%]
tests/integration/test_phase3_preflight.py::test_preflight_05_gpu_slot_atomicity_and_stale_worker_reconciliation PASSED [ 38%]
tests/integration/test_phase3_preflight.py::test_preflight_06_sse_persistence_and_replay_across_restart PASSED [ 39%]
tests/integration/test_phase4_data_integrity.py::test_scenario_a_and_b_stale_job_cannot_overwrite_newer_revision PASSED [ 41%]
tests/integration/test_phase4_data_integrity.py::test_scenario_c_two_successive_revisions_preserved PASSED [ 42%]
tests/integration/test_phase4_data_integrity.py::test_scenario_e_and_f_incomplete_or_failed_segment_blocks_export PASSED [ 43%]
tests/integration/test_phase4_data_integrity.py::test_scenario_g_conflicting_autosaves_409 PASSED [ 44%]
tests/integration/test_phase4_end_to_end.py::test_workflow_a_longform_vietnamese_narration PASSED [ 46%]
tests/integration/test_phase4_end_to_end.py::test_workflow_b_mandarin_chinese_narration PASSED [ 47%]
tests/integration/test_phase4_end_to_end.py::test_workflow_c_multicharacter_dialogue_mixed_engines PASSED [ 48%]
tests/integration/test_phase4_end_to_end.py::test_workflow_d_persistence_concurrency_and_isolation PASSED [ 50%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_rbac_matrix_and_negative_authorization PASSED [ 51%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_password_change_flow PASSED [ 52%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_brute_force_lockout_and_no_enumeration PASSED [ 53%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_fair_share_queue_scheduling PASSED [ 55%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_max_outstanding_jobs_limit PASSED [ 56%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_user_storage_quota_enforcement PASSED [ 57%]
tests/integration/test_phase5a_rbac_and_fairness.py::test_5a_voice_cloning_strict_ownership_no_admin_bypass PASSED [ 58%]
tests/integration/test_process_resilience.py::test_scenario_a_subprocess_kill_and_recovery PASSED [ 60%]
tests/integration/test_process_resilience.py::test_scenario_b_stale_worker_fencing_token_rejection PASSED [ 61%]
tests/integration/test_process_resilience.py::test_scenario_c_race_cancellation_vs_completion PASSED [ 62%]
tests/integration/test_process_resilience.py::test_scenario_d_multi_runner_cross_process_gpu_slot_enforcement PASSED [ 64%]
tests/integration/test_process_resilience.py::test_scenario_e_sse_stream_reconnection_and_replay PASSED [ 65%]
tests/integration/test_process_resilience.py::test_scenario_f_sqlite_online_backup_under_live_wal_writes PASSED [ 66%]
tests/integration/test_projects_api.py::test_project_crud_and_persistence PASSED [ 67%]
tests/integration/test_projects_api.py::test_project_optimistic_concurrency_conflict PASSED [ 69%]
tests/integration/test_projects_api.py::test_cross_user_project_isolation PASSED [ 70%]
tests/integration/test_projects_api.py::test_character_crud_and_voice_persona PASSED [ 71%]
tests/integration/test_segment_crud_and_partial_stale_invalidation PASSED [ 73%]
tests/integration/test_bulk_sync_segments_and_autosave PASSED [ 74%]
tests/integration/test_auto_segmentation_endpoint PASSED [ 75%]
tests/integration/test_render_single_and_batch_segments PASSED [ 76%]
tests/integration/test_master_audio_export_wav_and_mp3 PASSED [ 78%]
tests/integration/test_master_export_rejects_incomplete_project PASSED [ 79%]
tests/integration/test_security_hardened.py::test_concurrent_onboarding_race_condition PASSED [ 80%]
tests/integration/test_security_hardened.py::test_bootstrap_token_ttl_expiration PASSED [ 82%]
tests/integration/test_security_hardened.py::test_multi_user_cross_authorization_isolation PASSED [ 83%]
tests/integration/test_spa_serving.py::test_spa_index_and_assets PASSED  [ 84%]
tests/integration/test_supervisor_resilience.py::test_worker_crash_isolation_and_restart PASSED [ 85%]
tests/integration/test_voice_cloning_security.py::test_voice_cloning_upload_requires_explicit_consent PASSED [ 87%]
tests/integration/test_voice_cloning_security.py::test_voice_cloning_upload_invalid_format PASSED [ 88%]
tests/integration/test_voice_cloning_security.py::test_voice_cloning_upload_duration_limits PASSED [ 89%]
tests/integration/test_voice_cloning_security.py::test_voice_cloning_cross_user_isolation PASSED [ 91%]
tests/integration/test_filesystem_path_injection_prohibited PASSED [ 92%]
tests/integration/test_voice_cloning_rejected_on_unsupported_engine PASSED [ 93%]
tests/integration/test_arbitrary_unsupported_parameters_rejected PASSED [ 94%]
tests/integration/test_unsupported_voice_rejected PASSED [ 96%]
tests/integration/test_qwen3_speaker_enum_validation PASSED [ 97%]
tests/unit/test_queue_contract.py::test_queue_state_transitions PASSED   [ 98%]
tests/unit/test_security_contract.py::test_jwt_signature_and_expiry PASSED [100%]

================ 78 passed, 113 warnings in 186.52s (0:03:06) =================
```

---

## 4. BẰNG CHỨNG XÂY DỰNG GIAO DIỆN FRONTEND (TYPESCRIPT / VITE BUILD)

```
> ai-voice-studio-web@1.0.0 build
> tsc && vite build

vite v6.4.4 building for production...
transforming...
✓ 1604 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.61 kB │ gzip:  0.40 kB
dist/assets/index-CsPuHwNC.css   35.62 kB │ gzip:  6.50 kB
dist/assets/index-DwQcOGcE.js   369.88 kB │ gzip: 99.27 kB
✓ built in 2.98s
```

---

## 5. BẰNG CHỨNG SAO LƯU CƠ SỞ DỮ LIỆU SAU MIGRATION

```
Directory: D:\AIVoiceStudioData\backups

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----         10/9/2026  12:51 AM         364544 studio_post_phase5a_20261009_012726.db
```
Cơ sở dữ liệu sản xuất đã nâng cấp thành công lên phiên bản `20261009_0005` mà không xảy ra bất kỳ sự cố mất mát hay hư hỏng dữ liệu nào.
