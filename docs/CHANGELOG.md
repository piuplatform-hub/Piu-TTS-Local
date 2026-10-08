# Documentation changelog

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
