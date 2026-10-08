# AI VOICE STUDIO — PHASE 4 TEST EVIDENCE
## TWO-TIER REGRESSION SUITE & REAL CHROME BROWSER E2E VERIFICATION

**Ngày kiểm thử**: 2026-10-08  
**Môi trường thử nghiệm**:
- Hệ điều hành: Windows 11 Pro 64-bit
- Vi xử lý: Intel Core i5-12400F (6 Cores / 12 Threads)
- Card đồ họa: NVIDIA GeForce RTX 3050 (6GB VRAM, CUDA 12.8)
- Bộ nhớ RAM: 16 GB DDR4
- FFmpeg: Version 7.1.1-essentials_build-www.gyan.dev
- Trình duyệt: Google Chrome 142.x (x64) via Playwright

---

## 1. TỔNG HỢP KẾT QUẢ KIỂM THỬ

### 1.1. Pytest Backend Suite: 67/67 PASSED (100%)
Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/unit/ tests/integration/ -v
```
Thời gian thực thi: **142.03s (0:02:22)**

Chi tiết từng nhóm kiểm thử:
1. **Unit Tests (Text Segmentation Engine)**:
   - `tests/unit/test_text_segmenter.py::test_segmenter_vietnamese_sentence_boundaries`: PASSED
   - `tests/unit/test_text_segmenter.py::test_segmenter_vietnamese_multi_paragraph`: PASSED
   - `tests/unit/test_text_segmenter.py::test_segmenter_mandarin_sentence_boundaries`: PASSED

2. **Phase 4 Workspace & DSP API Integration**:
   - `tests/integration/test_projects_api.py::test_project_crud_and_persistence`: PASSED
   - `tests/integration/test_projects_api.py::test_project_optimistic_concurrency_conflict`: PASSED
   - `tests/integration/test_projects_api.py::test_cross_user_project_isolation`: PASSED
   - `tests/integration/test_projects_api.py::test_character_crud_and_voice_persona`: PASSED
   - `tests/integration/test_projects_api.py::test_segment_crud_and_partial_stale_invalidation`: PASSED
   - `tests/integration/test_projects_api.py::test_bulk_sync_segments_and_autosave`: PASSED
   - `tests/integration/test_projects_api.py::test_auto_segmentation_endpoint`: PASSED
   - `tests/integration/test_projects_api.py::test_render_single_and_batch_segments`: PASSED
   - `tests/integration/test_projects_api.py::test_master_audio_export_wav_and_mp3`: PASSED
   - `tests/integration/test_projects_api.py::test_master_export_rejects_incomplete_project`: PASSED

3. **Phase 4 End-to-End Workflows**:
   - `tests/integration/test_phase4_end_to_end.py::test_workflow_a_longform_vietnamese_narration`: PASSED
   - `tests/integration/test_phase4_end_to_end.py::test_workflow_b_mandarin_chinese_narration`: PASSED
   - `tests/integration/test_phase4_end_to_end.py::test_workflow_c_multicharacter_dialogue_mixed_engines`: PASSED
   - `tests/integration/test_phase4_end_to_end.py::test_workflow_d_persistence_concurrency_and_isolation`: PASSED

4. **Database Migrations (Alembic Head `20261008_0004`)**:
   - `tests/integration/test_migrations.py::test_alembic_fresh_database_upgrade`: PASSED
   - `tests/integration/test_migrations.py::test_alembic_upgrade_preexisting_db_without_data_loss`: PASSED
   - `tests/integration/test_migrations.py::test_foreign_key_constraint_enforcement`: PASSED
   - `tests/integration/test_migrations.py::test_sqlite_wal_mode_enabled`: PASSED

5. **Durable Jobs Queue & Concurrency Invariants (Phase 2 Baseline)**:
   - 14/14 tests trong `test_durable_jobs.py`: PASSED (Bao gồm Atomic Claim, Fencing Token, Lease Reclaiming, Exponential Backoff, Short Transactions).

6. **Worker Supervisor & Resilience (Phase 2 & Phase 3 Baseline)**:
   - 6/6 tests trong `test_process_resilience.py`: PASSED (Bao gồm Subprocess kill recovery, Stale worker rejection, Multi-runner slot enforcement, SQLite WAL live backup).
   - 6/6 tests trong `test_phase3_preflight.py`: PASSED.

7. **Voice Cloning Security & Path Traversal Guards (Phase 3 Baseline)**:
   - 9/9 tests trong `test_voice_cloning_security.py`: PASSED (Bao gồm Consent validation, Duration limits, Cross-user isolation, Path traversal rejection).

---

## 2. REAL CHROME BROWSER E2E TEST EVIDENCE

Lệnh thực thi:
```powershell
.venv\Scripts\python.exe -m pytest tests/e2e/test_phase4_browser_e2e.py -v -s
```
Kết quả: **PASSED (1/1 trong 6.50s)**

### 2.1. Quá trình kiểm chứng tự động:
1. **Khởi tạo và Di chuyển CSDL**: Alembic chạy nâng cấp tự động qua 4 revisions lên head `20261008_0004`.
2. **Onboarding**: Đăng ký tài khoản Quản trị viên `studio_master` bằng bootstrap token dùng một lần.
3. **Điều hướng Projects Workspace**: Tải giao diện `ProjectsView` và hiển thị danh mục rỗng ban đầu.
4. **Tạo Dự án Sách Nói**: Điền tiêu đề `Sách Nói: Hào Khí Đông A`, chọn loại `narration` và chuyển vào `SpeechStudioView`.
5. **Tự động phân đoạn (Intelligent Segmentation)**: Dán văn bản dài tiếng Việt, gọi API phân đoạn, xem trước ranh giới câu và nạp thành công 3 phân đoạn vào kịch bản.
6. **Tạo Dự án Kịch Truyền Thanh**: Tạo dự án `Kịch Truyền Thanh: Gặp Gỡ Hà Nội`, chọn loại `dialogue` và chuyển vào `DialogueStudioView`.
7. **Tạo Hồ sơ Nhân vật (Character Persona)**:
   - Tạo nhân vật `Lan (Hà Nội)` gán động cơ `VieNeu-TTS` (Mai Anh).
   - Tạo nhân vật `Mei (Du Khách)` gán động cơ `Qwen3-TTS` (Vivian).
8. **Biên tập luồng thoại**: Thêm câu thoại, gán vai nhân vật và điều chỉnh khoảng lặng chuyển lượt nói `pause_after_ms`.
9. **Master Audio Export (DSP Modal)**: Mở hộp thoại Master Export, xác nhận cấu hình WAV 48kHz, tùy chọn chuẩn hóa âm lượng EBU R128 (-16 LUFS) và đóng modal an toàn.

### 2.2. Danh mục Ảnh chụp màn hình Authentic đã lưu:
- `docs/reports/screenshots/phase4_01_project_created.png` (Kích thước: 69.2 KB)
- `docs/reports/screenshots/phase4_02_speech_studio_segmented.png` (Kích thước: 90.7 KB)
- `docs/reports/screenshots/phase4_03_dialogue_studio_characters.png` (Kích thước: 79.1 KB)
- `docs/reports/screenshots/phase4_04_dialogue_script_stream.png` (Kích thước: 95.8 KB)
- `docs/reports/screenshots/phase4_05_master_export_modal.png` (Kích thước: 145.4 KB)
