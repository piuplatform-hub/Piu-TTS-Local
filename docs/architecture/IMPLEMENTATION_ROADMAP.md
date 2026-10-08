# IMPLEMENTATION ROADMAP & PHASED VERIFICATION PLAN (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-RDM-001-R1  
**Status:** R1.1 — PROPOSED / PENDING OWNER APPROVAL (documentation revision only)  
**Date:** October 2026  

> **Canonical contract:** [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). This R1.1 text is a design proposal, not evidence of implementation or measured performance. For contradictions, canonical contracts and accepted ADRs take precedence.

---

## 1. Roadmap Strategy: Vertical Slices & Early Feasibility Spike

The revised roadmap **R1** eliminates the risk of late-stage UI failure or unforeseen AI model incompatibilities by introducing two fundamental adjustments:
1. **Early UI Foundation & Vertical Slice in Phase 1:** Build the core application shell, navigation, design system, and job progress components alongside the Mock Engine so that end-to-end user interaction is proven from the very beginning.
2. **Early Engine Feasibility Spike (Phase 1B Gate):** Conduct controlled benchmarks on real AI models (VieNeu on CPU, Qwen3 on RTX 3050) early in the schedule to empirically measure RAM/VRAM peaks, RTF, and Windows 11 compatibility *before* investing deep effort into studio interfaces.

```
[Phase 0: Architecture Review R1] ─────────────► (Current Phase - Approved in Principle)
       │
       ▼
[Phase 1: Foundation, Mock Engine & UI Shell] ──► Monorepo, DB, Auth, Mock Engine, React Shell
       │
       ▼
[Phase 1B: Early Engine Feasibility Spike] ─────► Measure real VRAM, RAM, RTF on RTX 3050 & i5
       │
       ▼
[Phase 2: Durable Queue & Core Services] ──────► Lease fencing, persistent events, restart recovery
       │
       ▼
[Phase 3: Production Engine Integration] ──────► Production VieNeu (CPU) & Qwen3 (GPU 6GB) Adapters
       │
       ▼
[Phase 4: Professional Studio UX & DSP] ───────► Speech, Clone & Dialogue Studios, FFmpeg EBU R128
       │
       ▼
[Phase 5: Multi-User LAN & Windows Packaging] ──► Caddy TLS, RBAC, Tray Daemon, Inno Setup Installer
       │
       ▼
[Phase 6: Hardening, MCP & v1.0 Release] ──────► Nightly Backups, Security Audit, MCP Adapter, v1.0
```

---

## 2. Phase-by-Phase Execution Plan

### Phase 0: Discovery, Architecture & Approval R1 *(Current Phase)*
* **Objectives:** Systematic review of host environment, critical evaluation of assumptions, and creation of revised architecture specification (R1).
* **Dependencies:** None.
* **Deliverables:** Complete `docs/architecture/` suite updated to Revision R1.
* **Exit Conditions:** Formal approval from project owner.

---

### Phase 1: Platform Foundation, Mock Engine & Shared UI Shell
* **Objectives:** Establish clean monorepo, set up database migrations, implement authentication foundation (Onboarding Wizard), Engine SDK contract, Mock Engine, and shared React UI shell.
* **Dependencies:** Phase 0 approval.
* **Deliverables:**
  * Clean monorepo (`apps/server`, `apps/web`, `packages/engine_sdk`, `engines/mock`).
  * SQLite WAL database with SQLAlchemy 2.0 models and Alembic migrations.
  * Identity module with Argon2id password hashing and Onboarding Wizard API.
  * `engine.manifest.json` schema validator and Mock Engine running on ephemeral loopback HTTP.
  * React 19 UI Shell with navigation sidebar, dark/light theme, and live job status badge.
* **Acceptance Criteria & Test Evidence:**
  * `pytest tests/contract/test_mock_engine.py` passes on the real dev environment; report collected/pass/skipped counts and failures.
  * Secure one-time local bootstrap blocks concurrent duplicate admin creation; subsequent visit requires login.
  * **Complete minimal vertical slice:** enter text → submit to Mock Engine (development-only single-process dispatcher) → observe status → play and download verified WAV.
  * OpenAPI schema is generated and the frontend TypeScript client is typechecked against it.
* **Exit Condition:** Mock audio workflow works end-to-end in browser, auth/contract tests pass, no neural weights used; **production durability is NOT claimed until Phase 2**.

---

### Phase 1B: Early Engine Feasibility Spike (Gate Review)
* **Objectives:** Measure empirical performance and stability of real models on the host machine in isolated test scripts *without* building full production adapters yet.
* **Spike Checklist:**
  1. Measure VieNeu-TTS v3 Turbo ONNX inference latency, RTF, and RAM peak on Intel i5-12400F.
  2. Verify 3–5 second Vietnamese voice cloning audio quality from sample.
  3. Load `Qwen3-TTS-0.6B-CustomVoice` on RTX 3050 via PyTorch CUDA; record baseline VRAM consumption and peak VRAM during synthesis of 50, 100, and 250 words.
  4. Confirm Python 3.12 compatibility on Windows 11 without C++ compilation errors.
* **Exit Condition:** Separately approved spike report includes verified RAM/VRAM numbers, CPU/GPU RTF/latency and blockers. Phase 1 authorization **does not** authorize model installs or Phase 1B.

---

### Phase 2: Headless Core, Durable Lease Queue & End-to-End Workflow
* **Objectives:** Harden the already-functioning Mock Engine vertical slice with atomic job leasing, fencing, restart recovery, SSE persisted event replay and cancellation.
* **Dependencies:** Phase 1 & Phase 1B.
* **Deliverables:**
  * Async `JobScheduler` with atomic leases (`BEGIN IMMEDIATE RETURNING`) and heartbeat renewal.
  * Server-Sent Events hub supporting client reconnect via `Last-Event-ID`.
  * Standalone static FFmpeg integration for waveform generation.
  * Working end-to-end slice: User enters text in UI $\rightarrow$ Job enqueued $\rightarrow$ Progress bar updates $\rightarrow$ Mock audio played in browser player.
* **Acceptance Criteria & Test Evidence:**
  * Simulated worker crash results in safe reconciliation and policy-driven recovery, with no simultaneous duplicate attempt and no stale artifact publication.
  * Two scheduler contenders never claim one queued job concurrently; SSE reconnect uses persisted `job_events` or documented fallback.
* **Exit Condition:** Durable queue correctness demonstrated by concurrent claim, worker-crash, restart, cancellation and file/DB fault-injection tests.

---

### Phase 3: Production Real Engine Adapters Integration
* **Objectives:** Build production-grade, isolated adapters for VieNeu-TTS and Qwen3-TTS incorporating telemetry-driven resource scheduling.
* **Dependencies:** Phase 2 & Phase 1B findings.
* **Deliverables:**
  * `engines/vieneu/`: Production adapter running on ONNX CPU with preset voices and voice cloning.
  * `engines/qwen3/`: Production adapter running on CUDA with CustomVoice presets (Vivian, Uncle Fu).
  * `ResourceAwareScheduler`: Global GPU Mutex and dynamic NVML VRAM threshold pre-flight check.
* **Acceptance Criteria & Test Evidence:**
  * Real Vietnamese audio synthesized on the selected CPU backend, with measured per-process RAM use and GPU telemetry; do not assert exactly zero VRAM usage without evidence.
  * Real Chinese audio synthesized via RTX 3050 within measured safe VRAM boundaries.
  * Simultaneous submission of Vietnamese and Chinese jobs schedules safely without CUDA OOM.
* **Exit Condition:** Both real engines operating reliably via Engine SDK.

---

### Phase 4: Professional Studio UX & Audio DSP Pipeline
* **Objectives:** Build high-fidelity user interface matching the product vision: Speech Studio, Voice Cloning Studio, Dialogue Studio, and Master Audio Export.
* **Dependencies:** Phase 3.
* **Deliverables:**
  * **Speech Studio:** Rich script editor, engine/voice selector, parameter sliders, audio player.
  * **Voice Cloning Studio:** Sample audio uploader, consent declaration gate, instant preview.
  * **Dialogue Studio:** Multi-speaker table (alternating Vietnamese & Chinese), per-line render, silence duration control, and master export button.
  * **Audio DSP Pipeline:** Concat and EBU R128 loudness normalization via FFmpeg.
* **Acceptance Criteria & Test Evidence:**
  * Multi-character dialogue combining VieNeu and Qwen3 exported as a single balanced WAV master track.
* **Exit Condition:** Complete, professional content-creation workflow verified by end users.

---

### Phase 5: Multi-User LAN Server, Windows Tray Daemon & Native Packaging
* **Objectives:** Enable safe office LAN sharing and provide a professional Windows desktop experience.
* **Dependencies:** Phase 4.
* **Deliverables:**
  * Role-Based Access Control enforcement (Admin, Editor, Viewer).
  * LAN Reverse Proxy configuration (Caddy TLS) and Host/Origin validation middleware.
  * Windows System Tray background daemon (`studio-tray.py` / executable) keeping server alive when windows close.
  * Inno Setup script generating a professional Windows Installer (`.exe`).
* **Acceptance Criteria & Test Evidence:**
  * Remote laptop on LAN logs into server via HTTPS and renders audio through shared RTX 3050.
* **Exit Condition:** Multi-user office LAN operations validated.

---

### Phase 6: Hardening, Observability, MCP & v1.0 Release
* **Objectives:** Production hardening, automated tested recovery backups, comprehensive documentation. MCP adapter remains a separately approved **optional** extension, not a v1.0 release blocker.
* **Dependencies:** Phase 5.
* **Deliverables:**
  * Nightly online SQLite backup (`.backup`) and artifact retention garbage collection.
  * RFC 9457 structured logging and admin health monitoring dashboard.
  * Optional (separate approval): MCP Server proof-of-concept exposing a constrained subset of TTS tools via authorized application services.
  * Final Production Release v1.0.
* **Exit Condition:** v1.0 signed off for daily production use.
