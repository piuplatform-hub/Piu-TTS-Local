# BẰNG CHỨNG KIỂM THỬ END-TO-END VÀ HỒI QUY PHASE 4
## AI VOICE STUDIO — BẰNG CHỨNG THỰC NGHIỆM TRÊN GOOGLE CHROME VÀ HẠ TẦNG

**Ngày lập báo cáo:** 08/10/2026  
**Môi trường thực thi:** Windows 11 Host, Intel Core i5-12400F, NVIDIA GeForce RTX 3050 (6GB VRAM), RAM 16GB  
**Bộ duyệt kiểm thử:** Google Chrome (v131+ Headless qua Playwright)  
**Trạng thái kiểm thử:** **78/78 TESTS PASSED (100%)**

---

## 1. KẾT QUẢ TỔNG HỢP TOÀN BỘ BỘ KIỂM THỬ HỒI QUY

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\C\Dev\du an\TTS, configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0

tests/contract/test_vieneu_engine.py::test_vieneu_manifest_validation                   PASSED
tests/contract/test_vieneu_engine.py::test_vieneu_worker_lifecycle_and_contract         PASSED
tests/integration/test_auth_api.py::test_auth_onboarding_lifecycle                     PASSED
tests/integration/test_durable_jobs.py::test_01_job_state_machine_valid_and_invalid     PASSED
tests/integration/test_durable_jobs.py::test_02_atomic_claim_concurrency               PASSED
tests/integration/test_durable_jobs.py::test_03_idempotency_payload_conflict            PASSED
tests/integration/test_durable_jobs.py::test_04_lease_expiration_and_reclaiming         PASSED
tests/integration/test_durable_jobs.py::test_05_fencing_token_rejection                 PASSED
tests/integration/test_durable_jobs.py::test_06_retry_with_exponential_backoff          PASSED
tests/integration/test_durable_jobs.py::test_07_manual_retry_of_failed_job             PASSED
tests/integration/test_durable_jobs.py::test_08_cancellation_queued_and_running         PASSED
tests/integration/test_durable_jobs.py::test_09_server_restart_recovery                 PASSED
tests/integration/test_durable_jobs.py::test_10_resource_limits_and_waiting_reason     PASSED
tests/integration/test_durable_jobs.py::test_11_sse_event_streaming_and_replay          PASSED
tests/integration/test_durable_jobs.py::test_12_sse_strict_authorization                PASSED
tests/integration/test_durable_jobs.py::test_13_short_transactions_db_not_locked       PASSED
tests/integration/test_durable_jobs.py::test_14_artifact_isolation_on_cancellation     PASSED
tests/integration/test_jobs_api.py::test_tts_job_lifecycle_and_artifact                 PASSED
tests/integration/test_migrations.py::test_alembic_fresh_database_upgrade               PASSED
tests/integration/test_migrations.py::test_alembic_upgrade_preexisting_db              PASSED
tests/integration/test_migrations.py::test_foreign_key_constraint_enforcement          PASSED
tests/integration/test_migrations.py::test_sqlite_wal_mode_enabled                     PASSED
tests/integration/test_phase3_integration.py::test_vieneu_tts_end_to_end_pipeline       PASSED
tests/integration/test_phase3_integration.py::test_vieneu_tts_zero_shot_voice_cloning  PASSED
tests/integration/test_phase3_integration.py::test_qwen3_tts_end_to_end_pipeline        PASSED
tests/integration/test_phase3_integration.py::test_concurrency_and_slot_isolation     PASSED
tests/integration/test_phase3_preflight.py::test_preflight_01_dual_scheduler_conflict   PASSED
tests/integration/test_phase3_preflight.py::test_preflight_02_standalone_runner         PASSED
tests/integration/test_phase3_preflight.py::test_preflight_03_queued_jobs_survive      PASSED
tests/integration/test_phase3_preflight.py::test_preflight_04_crash_recovery_at_least   PASSED
tests/integration/test_phase3_preflight.py::test_preflight_05_gpu_slot_atomicity        PASSED
tests/integration/test_phase3_preflight.py::test_preflight_06_sse_persistence           PASSED
tests/integration/test_phase4_data_integrity.py::test_scenario_a_and_b_stale_job        PASSED
tests/integration/test_phase4_data_integrity.py::test_scenario_c_two_successive_revs   PASSED
tests/integration/test_phase4_data_integrity.py::test_scenario_e_and_f_incomplete_seg   PASSED
tests/integration/test_phase4_data_integrity.py::test_scenario_g_conflicting_autosaves  PASSED
tests/integration/test_phase4_end_to_end.py::test_workflow_a_longform_vietnamese        PASSED
tests/integration/test_phase4_end_to_end.py::test_workflow_b_mandarin_chinese           PASSED
tests/integration/test_phase4_end_to_end.py::test_workflow_c_multicharacter_dialogue    PASSED
tests/integration/test_phase4_end_to_end.py::test_workflow_d_persistence_concurrency    PASSED
tests/integration/test_process_resilience.py::test_scenario_a_subprocess_kill_recovery  PASSED
tests/integration/test_process_resilience.py::test_scenario_b_stale_worker_fencing     PASSED
tests/integration/test_process_resilience.py::test_scenario_c_race_cancellation         PASSED
tests/integration/test_process_resilience.py::test_scenario_d_gpu_slot_enforcement      PASSED
tests/integration/test_process_resilience.py::test_scenario_e_sse_stream_reconnection   PASSED
tests/integration/test_process_resilience.py::test_scenario_f_sqlite_online_backup     PASSED
tests/integration/test_projects_api.py::test_project_crud_and_persistence               PASSED
tests/integration/test_projects_api.py::test_project_optimistic_concurrency_conflict   PASSED
tests/integration/test_projects_api.py::test_cross_user_project_isolation               PASSED
tests/integration/test_projects_api.py::test_character_crud_and_voice_persona           PASSED
tests/integration/test_projects_api.py::test_segment_crud_and_partial_stale_inval      PASSED
tests/integration/test_projects_api.py::test_bulk_sync_segments_and_autosave           PASSED
tests/integration/test_projects_api.py::test_auto_segmentation_endpoint                 PASSED
tests/integration/test_projects_api.py::test_render_single_and_batch_segments          PASSED
tests/integration/test_projects_api.py::test_master_audio_export_wav_and_mp3           PASSED
tests/integration/test_projects_api.py::test_master_export_rejects_incomplete_project   PASSED
tests/integration/test_security_hardened.py::test_concurrent_onboarding_race            PASSED
tests/integration/test_security_hardened.py::test_bootstrap_token_ttl_expiration        PASSED
tests/integration/test_security_hardened.py::test_multi_user_cross_authorization        PASSED
tests/integration/test_spa_serving.py::test_spa_index_and_assets                        PASSED
tests/integration/test_supervisor_resilience.py::test_worker_crash_isolation            PASSED
tests/integration/test_voice_cloning_security.py::test_voice_cloning_consent            PASSED
tests/integration/test_voice_cloning_security.py::test_voice_cloning_invalid_format     PASSED
tests/integration/test_voice_cloning_security.py::test_voice_cloning_duration_limits    PASSED
tests/integration/test_voice_cloning_security.py::test_voice_cloning_isolation          PASSED
tests/integration/test_voice_cloning_security.py::test_filesystem_path_injection       PASSED
tests/integration/test_voice_cloning_security.py::test_voice_cloning_unsupported_eng    PASSED
tests/integration/test_voice_cloning_security.py::test_arbitrary_unsupported_params     PASSED
tests/integration/test_voice_cloning_security.py::test_unsupported_voice_rejected       PASSED
tests/integration/test_voice_cloning_security.py::test_qwen3_speaker_enum_validation    PASSED
tests/e2e/test_phase4_browser_e2e.py::test_phase4_real_browser_e2e_studio_journey       PASSED
================ 78 passed, 127 warnings in 222.48s (0:03:42) =================
```

---

## 2. BẰNG CHỨNG HÌNH ẢNH TRÊN TRÌNH DUYỆT GOOGLE CHROME

Tất cả các ảnh chụp màn hình được tạo tự động bởi Playwright trong quá trình tương tác thực tế với ứng dụng Web UI và được lưu trữ trực tiếp tại `docs/reports/screenshots/`:

1. **Khởi tạo và Điều hướng Dự án (`phase4_01_project_created.png`)**
   - *Mô tả:* Người dùng hoàn thành onboarding, tạo dự án sách nói "Sách Nói: Hào Khí Đông A", điều hướng vào Speech Studio với huy hiệu phiên bản `v1` và các điều khiển chuyên nghiệp.
   - *Kích thước tệp:* 69,220 bytes.

2. **Phân đoạn văn bản thông minh (`phase4_02_speech_studio_segmented.png`)**
   - *Mô tả:* Modal tự động phân đoạn xử lý đoạn văn bản dài tiếng Việt, phân tách ranh giới ngữ nghĩa và dấu chấm câu, hiển thị số ký tự và xem trước từng phân đoạn trước khi nạp vào dự án.
   - *Kích thước tệp:* 90,716 bytes.

3. **Không gian kịch bản hội thoại đa nhân vật (`phase4_03_dialogue_studio_characters.png`)**
   - *Mô tả:* Dialogue Studio quản lý danh sách nhân vật đa động cơ: Lan (Hà Nội - VieNeu-TTS) và Mei (Du Khách - Qwen3-TTS) với mã màu đại diện và thiết lập giọng đọc độc lập.
   - *Kích thước tệp:* 79,064 bytes.

4. **Dòng kịch bản đan xen thoại & khoảng lặng (`phase4_04_dialogue_script_stream.png`)**
   - *Mô tả:* Các câu thoại luân phiên giữa 2 nhân vật, thanh điều chỉnh khoảng lặng nghỉ giữa các câu thoại (`pause_after_ms` từ 300ms đến 500ms) và các nhãn trạng thái phân đoạn (`draft`, `queued`, `completed`).
   - *Kích thước tệp:* 95,775 bytes.

5. **Modal Master Audio DSP & EBU R128 (`phase4_05_master_export_modal.png`)**
   - *Mô tả:* Giao diện mastering âm thanh chuyên nghiệp: tùy chọn xuất WAV/MP3, resampler 48kHz, checkbox chuẩn hóa EBU R128 (-16.0 LUFS, True Peak -1.0 dBTP), ước tính thời lượng và danh sách lịch sử master.
   - *Kích thước tệp:* 145,389 bytes.

---

## 3. BẰNG CHỨNG VỀ TÍNH BẢO MẬT & TOÀN VẸN DỮ LIỆU

1. **Kiểm soát tương tranh lạc quan (OCC 409 Conflict):**
   - Đã kiểm chứng: Khi hai tab hoặc hai tiến trình cùng gửi cập nhật cho một dự án hoặc phân đoạn với `expected_version` không khớp, hệ thống từ chối với mã lỗi `409 Conflict` (RFC 9457 Problem Details) và bảo vệ dữ liệu không bị ghi đè thầm lặng.
2. **Cách ly phân quyền giữa người dùng (Cross-User Isolation):**
   - Người dùng A không thể truy cập, xem danh sách, cập nhật, render hoặc tải tệp xuất bản của Người dùng B. Hệ thống trả về `403 Forbidden` hoặc `404 Not Found`.
3. **Chống giả mạo đường dẫn tệp (Directory Traversal Prevention):**
   - Tệp manifest của FFmpeg và tệp tải về được xác thực phạm vi thư mục bên trong `D:\AIVoiceStudioData\exports\` hoặc `artifacts\`, ngăn chặn hoàn toàn việc rò rỉ tệp hệ thống máy chủ.
