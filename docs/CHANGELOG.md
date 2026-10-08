# Documentation changelog

## 2026-10-08 — Phase 3 Acceptance Gate: Real Engine Audit, Secure Audio Pipeline & Full Regression Verified (Gate PASS)

- **Remediated Secure Voice Cloning Pipeline:** Eliminated server filesystem path injection vectors (`ref_audio`). Implemented `ReferenceAssetRecord` in `apps/server/src/models/asset.py` with Alembic migration `20261008_0003_reference_assets.py`. Created `AssetService` validating RIFF/WAVE headers (0.5s–30s duration, <=15MB), enforcing UUID server paths, cross-user authorization isolation (`403 Forbidden`), and requiring explicit user legal consent (`voice_use_consent`).
- **Engine Parameter Contract Hardening:** `DurableQueueService` strictly validates requested engine capabilities (`VOICE_CLONING_NOT_SUPPORTED`), manifests `parameters_schema` keys (`UNSUPPORTED_PARAMETER`), range limits for `speed` and enum for Qwen3 `speaker` (`INVALID_PARAMETER_VALUE`), and voice catalog membership (`UNSUPPORTED_VOICE`).
- **Frontend Voice Cloning UI Overhaul:** Upgraded `StudioView.tsx` with dedicated WAV file upload, library asset dropdown, and legal consent checkbox. Rebuilt production bundle (`apps/web/dist`) cleanly with 0 errors.
- **Two-Tier Regression Test Suite (100% PASS):** Executed full regression suite:
  - **Tier 1 (Fast CI Suite):** 42/42 tests passed in 52.24s (0 failed, 0 skipped).
  - **Tier 2 (Hardware Integration Suite):** 15/15 tests passed in 131.43s (0 failed, 0 skipped).
  - **Total:** 57/57 tests passing (100%).
- **Authentic Acceptance Audio Package Generated:** Produced 4 real WAV files in `D:\AIVoiceStudioData\acceptance_audio_phase3\` outside Git:
  1. `vi_male_haidang.wav`: VieNeu preset "Hải Đăng", 9.36s, 48kHz, RTF 1.39, SHA256: `b613c8f089dfbd06...`
  2. `vi_female_maianh.wav`: VieNeu preset "Mai Anh", 10.16s, 48kHz, RTF 0.62, SHA256: `4856259e21e7633d...`
  3. `vi_cloned_sample.wav`: VieNeu zero-shot clone from verified reference WAV, 9.20s, 48kHz, RTF 0.92, SHA256: `e76240d67c3e7845...`
  4. `zh_female_vivian.wav`: Qwen3 preset "Vivian" on CUDA GPU, 12.40s, 24kHz, RTF 2.48, SHA256: `bb55e28b67f71e69...`
- **Hardware Telemetry Verified:**
  - PyTorch CUDA allocated: 2,065.0 MB; Peak board VRAM (nvidia-smi): 3,523.0 MB / 6,144.0 MB (57.3% usage); 2,747.0 MB cleanly reclaimed post-shutdown.
  - VieNeu CPU worker RAM RSS: 2,444.0 MB, fully released upon worker termination.
- **Scientific Honesty & Governance Compliance:** Documented Qwen3 RTF > 1.0 (2.48) as slower-than-real-time; classified voice cloning perceptual quality as **UNVERIFIED HUMAN-PERCEIVED SIMILARITY**; retained external CUDA OOM risk boundaries.
- **Published Deliverables:** `PHASE_03_ACCEPTANCE_REVIEW.md`, `PHASE_03_FULL_REGRESSION.md`, and `PHASE_03_AUDIO_ACCEPTANCE.md`.

## 2026-10-08 — Phase 3 Production AI Engine Adapters & End-to-End Inference Integration Completed

- **Mandatory Pre-Flight Gate Verification:** Passed all 6 pre-flight gate tests (`test_phase3_preflight.py` in 4.03s), verifying dual-scheduler conflict prevention, standalone runner execution, crash recovery with at-least-once semantics, cross-process GPU slot atomicity, and SSE replay across server restarts.
- **Production Engine A (VieNeu-TTS v3 Turbo):** Implemented production adapter in `engines/vieneu/` running isolated in Python 3.12 (`vieneu_env`) on CPU via ONNX Runtime FP32. Supports 22 preset Vietnamese voices, zero-shot voice cloning with reference audio embedding extraction, and 48kHz WAV audio export. Verified with contract tests (`test_vieneu_engine.py` passed in 23.13s).
- **Production Engine B (Qwen3-TTS 0.6B CustomVoice):** Implemented production adapter in `engines/qwen3/` running isolated in Python 3.12 (`qwen3_env`) on GPU NVIDIA GeForce RTX 3050 (6GB VRAM, `bfloat16`). Supports 9 built-in speakers for Mandarin Chinese, 24kHz WAV export, CUDA OOM recovery, and strictly rejects voice cloning. Verified with contract tests (`test_qwen3_engine.py` passed in 78.74s).
- **Core Pipeline Upgrades:** Added `parameters: Dict[str, Any]` to `TTSJobSubmitRequest`, forwarded parameters through `DurableJobScheduler`, upgraded `ProcessSupervisor` to resolve absolute `virtualenv_path`, and increased `EngineWorkerClient` timeout to 180s.
- **Frontend UI Phase 3 Upgrade:** Upgraded `StudioView.tsx` with dynamic AI Engine dropdown, target device indicators (CPU vs GPU CUDA), preset voices, zero-shot voice cloning mode with reference WAV input and denoise toggle, and real-time audio playback for 24kHz and 48kHz WAV files. Production bundle cleanly rebuilt with 0 errors.
- **End-to-End Integration Tests:** Implemented `test_phase3_integration.py` passing 100% (4/4 passed in 67.44s) covering VieNeu 48kHz pipeline, VieNeu voice cloning, Qwen3 24kHz pipeline on RTX 3050, and CPU/GPU concurrency and slot isolation.
- **Real Chrome Browser E2E Playwright:** Implemented `test_phase3_browser_e2e.py` passing 100% in 20.17s; generated 6 authentic screenshots in `docs/reports/screenshots/` (0 console errors, 0 network failures).
- **Hardware Telemetry & Runtime Benchmarking:** Executed `scripts/benchmark_phase3_metrics.py`. Measured VieNeu warm RTF = 0.66 (faster than real-time), Qwen3 warm RTF = 1.63 (slower than real-time), Qwen3 allocated VRAM = 2,065 MB.
- **Published Deliverables:** `PHASE_03_ENGINE_INTEGRATION.md`, `PHASE_03_RUNTIME_METRICS.md`, `PHASE_03_IMPLEMENTATION_REPORT.md`, `PHASE_03_TEST_EVIDENCE.md`, and `PHASE_03_KNOWN_LIMITATIONS.md`.

## 2026-10-08 — Phase 2 Release Gate R1 Remediations Verified (Gate PASS)

- **P0 Security Remediated:** Eliminated JWT token query string parameter in SSE endpoint (`CWE-598`). Replaced browser `EventSource` with custom native `fetch()` streaming reader using `Authorization: Bearer` and `Last-Event-ID` HTTP headers in `apps/web/src/api/client.ts`. Backend `apps/server/src/api/v1/jobs.py` strictly rejects `?token=...` with HTTP `400 Bad Request` (`QUERY_AUTH_PROHIBITED`).
- **Decoupled Standalone Runner Process:** Added `apps/server/src/runner.py` allowing execution of `DurableJobScheduler` and inference worker supervision in an independent OS process separate from FastAPI. Added configuration setting `EMBEDDED_SCHEDULER` in `apps/server/src/config.py`. Proposed [ADR-0009](decisions/adr/ADR-0009-runner-process-and-online-backup.md).
- **Database-Backed Multi-Process Hardware Slot Enforcement:** `ResourceManager` enforces strict global hardware limits (max 1 GPU, max 1 CPU) across processes by querying active SQLite unexpired leases with self-counting prevention (`exclude_job_id`).
- **Safe SQLite Online Backup API & CLI Tool:** Created `BackupService` (`apps/server/src/services/backup_service.py`) and CLI `apps/server/src/backup.py` using `sqlite3.Connection.backup()` step-by-step (`pages=100`) for non-blocking live WAL backups. Verified `PRAGMA integrity_check` and safe restore. Audited existing database backups in `D:\AIVoiceStudioData` (`studio.db.phase1.bak` verified valid).
- **Process Failure Resilience Test Suite:** Implemented `tests/integration/test_process_resilience.py` validating 6 core failure scenarios (A through F): subprocess kill & recovery, fencing token stale worker rejection, race cancellation vs completion with zero orphan artifacts, multi-runner GPU slot limits, SSE stream reconnection & replay, and online backup during active WAL writes.
- **Automated Verification:** 34/34 tests passing (100%) in 22.62s; frontend production build cleanly regenerated (0 errors).
- **Published Deliverables:** `PHASE_02_RELEASE_GATE_REVIEW.md`, `PHASE_02_RELEASE_GATE_EVIDENCE.md`, and `PHASE_02_REMEDIATION_CHANGELOG.md`.

## 2026-10-08 — Phase 2 Durable Job Orchestration & Production Resilience Completed

- Backed up Phase 1 database: `D:\AIVoiceStudioData\studio.db.phase1.bak` and `D:\AIVoiceStudioData\backups\studio.db.phase1.bak`.
- Applied Alembic migration `20261008_0002_durable_jobs.py`: added priority, resource_type, attempt_count, max_retries, fencing token, locked_by, and created durable `job_events` table.
- Implemented `JobStateMachine` (`apps/server/src/services/job_state_machine.py`) with 6 explicit states (`queued`, `preparing`, `running`, `completed`, `failed`, `cancelled`) and `IllegalStateTransitionError`.
- Implemented `DurableQueueService` (`apps/server/src/services/durable_queue_service.py`): atomic claiming, fencing tokens (`current_attempt_id`), lease expiration reclaiming, exponential backoff retries, short transactions without SQLite locking during worker synthesis, and idempotency collision checks (`409 Conflict`).
- Implemented `ResourceManager` (`apps/server/src/services/resource_manager.py`): defensive slot limits (`max_gpu_slots = 1`, `max_cpu_slots = 1`, `max_global_slots = 2`) with waiting reasons.
- Implemented `DurableJobScheduler` daemon (`apps/server/src/supervisor/scheduler.py`) running in FastAPI lifespan, with startup crash recovery, background lease heartbeats, and graceful shutdown.
- Implemented Server-Sent Events (SSE) streaming (`GET /api/v1/jobs/{id}/events`) with query param token auth for EventSource, durable `job_events` persistence, and `Last-Event-ID` event replay.
- Updated Frontend UI (`StudioView.tsx`, `JobHistoryTable.tsx`, `client.ts`): cancel job button, manual retry button, attempt indicators, waiting reason badges, SSE real-time streaming with polling fallback, and reload persistence.
- Rebuilt frontend production bundle (`npm run build`).
- Automated testing expanded to 28 tests (100% passed in 18.30s), completely covering the 15 Phase 2 testing matrix categories and capturing 6 real Chrome browser Playwright screenshots.
- Published deliverables: `PHASE_02_DURABLE_QUEUE.md`, `PHASE_02_IMPLEMENTATION_REPORT.md`, `PHASE_02_TEST_EVIDENCE.md`, and `PHASE_02_KNOWN_LIMITATIONS.md`.
- Corrected Phase 1B documentation conclusions regarding total board VRAM, CUDA OOM risk boundaries, slower-than-real-time RTF, unverified concurrency, and voice cloning similarity status.

## 2026-10-08 — Phase 1B Engine Feasibility & Hardware Benchmark Completed

- Conducted pre-flight hardware and license verification for Intel Core i5-12400F and NVIDIA GeForce RTX 3050 (6GB VRAM) on Windows 11.
- Created isolated environments and model storage outside application repository (`D:\AIVoiceStudioData\benchmarks\`).
- Benchmarked VieNeu-TTS v3 Turbo on CPU (ONNX Runtime, torch-free): achieved RTF 0.55-0.75, 48kHz audio quality, 2.4GB peak RAM, zero memory leak across 5 repeated runs. Verdict: PASS.
- Benchmarked Qwen3-TTS 0.6B CustomVoice on GPU (PyTorch CUDA, bfloat16): peak VRAM only 2.77GB (well within 6GB limit), 24kHz audio, 9 preset speakers, error recovery verified in 4.4s. Verdict: PASS.
- Published benchmark deliverables: `PHASE_1B_ENVIRONMENT.md`, `VIENEU_BENCHMARK.md`, `QWEN3_BENCHMARK.md`, `PHASE_1B_COMPARISON.md`, and `PHASE_1B_FEASIBILITY_REPORT.md`.

## 2026-10-08 — Phase 1 Verification & Remediation Complete (Gate PH1 Ready)

- Revoked and redacted exposed bootstrap credential; implemented 15-minute TTL and atomic OS-level file rename (`os.replace`) preventing concurrent onboarding race conditions.
- Added multi-user RBAC service (`POST /api/v1/auth/users`) with role-based access control and strict artifact ownership cross-authorization isolation (403 Forbidden).
- Integrated Alembic database migration tooling (`alembic.ini`, `alembic/env.py`, initial revision `20261008_0001`) with automatic SQLite WAL and foreign key enforcement.
- Hardened Process Supervisor with native Windows Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) preventing orphan worker processes.
- Added explicit contract disclaimer banner to Web UI and rebuilt frontend production bundle.
- Executed real Google Chrome E2E test via Playwright across 12 user journey steps; recorded 5 authentic screenshots in `docs/reports/screenshots/` with 0 console errors and 0 network failures.
- Expanded automated test suite from 6 to 14 tests, achieving 100% pass rate (14/14 passed in 9.61s).
- Published verification reports: `PHASE_01_REVIEW_REPORT.md`, `PHASE_01_SECURITY_VERIFICATION.md`, `PHASE_01_E2E_TEST_RESULTS.md`, and `PHASE_01_REMEDIATION_CHANGELOG.md`.

## 2026-10-08 — Phase 1 Foundation & First Vertical Slice Completed

- Implemented Engine Adapter SDK v1 (`packages/engine_sdk`) with Pydantic v2 schemas and authenticated loopback HTTP client.
- Implemented Contract Mock Engine (`engines/mock`) generating pristine 16-bit PCM WAV audio with RFC 9457 error support.
- Built Headless Application Core (`apps/server`) with FastAPI, SQLite WAL persistence, Argon2id password hashing, JWT sessions, and one-time local bootstrap onboarding.
- Built Process Supervisor (`apps/server/src/supervisor`) with worker subprocess management, port allocation, and crash recovery.
- Built modern Web UI (`apps/web`) with React 19, TypeScript, Vite, and Tailwind CSS.
- Automated testing: 6/6 contract and integration tests passed (100%).
- Published reports: `PHASE_01_IMPLEMENTATION_REPORT.md`, `PHASE_01_TEST_EVIDENCE.md`, `PHASE_01_KNOWN_LIMITATIONS.md`, and `LOCAL_DEVELOPMENT.md`.

## 2026-10-08 — R1.1 Documentation Baseline Accepted (Gate DOC Passed)

- Product Owner formally accepted the Architecture R1.1 documentation pack as the official architectural baseline.
- Updated all 8 ADRs (ADR-0001 through ADR-0008) status to `accepted` under Product Owner authority.
- Recorded explicit condition: Hardware, GPU memory, inference latency, model audio quality, and Windows compatibility assumptions remain UNVERIFIED pending Phase 1B benchmarks.
- Published review report: `docs/reports/reviews/2026-10-08-documentation-acceptance.md`.
- Phase 1 implementation remains pending separate authorization (Gate PH1).

## 2026-10-08 — R1.1 (Proposed)

- Imported 9 Gemini R1 documents and kept exact originals in `archive/r1-original/`.
- Created long-term docs hierarchy, governance, versioned ADR register, phase plan, reports, ideas/research/specs/operations and templates.
- Reconciled canonical TTS API path (`/api/v1/jobs/speech`), safer SQLite claim/recovery semantics and stale worker fencing design.
- Hardened first-run bootstrap design; clarified plugin integrity is not signature/authenticity.
- Updated MCP design reference to 2026-07-28; qualified FFmpeg distribution obligations.
- Unified Phase 1 minimal mocked end-to-end acceptance and separated Phase 1B permissions.
- Marked model GPU figures as unverified pending benchmarks.

**Note:** This changelog records documentation edits only, not code or tests executed on the PC.
