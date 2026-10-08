# TECHNOLOGY DECISIONS & ARCHITECTURAL DECISION RECORDS (ADR) — REVISION R1
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-ADR-001-R1  
**Status:** R1.1 — PROPOSED / PENDING OWNER APPROVAL (documentation revision only)  
**Date:** October 2026  

> **Canonical contract:** [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). This R1.1 text is a design proposal, not evidence of implementation or measured performance. For contradictions, canonical contracts and accepted ADRs take precedence.

---

## 1. Technology Matrix Summary (Revision R1)

| Layer | Chosen Technology | Primary Alternatives Considered | Decisive Rationale in Revision R1 |
| :--- | :--- | :--- | :--- |
| **Backend Core** | **Python 3.12 + FastAPI + Pydantic v2** | Node.js (NestJS), Go, Django | Native OpenAPI, async I/O, seamless data structure exchange with AI modules, RFC 9457 error contracts. |
| **Database & ORM** | **SQLite (WAL Mode) + SQLAlchemy 2.0 + Alembic** | PostgreSQL, DuckDB | Single-file zero-daemon portability under Windows; safe atomic transactions; explicit acknowledgment of PG dialect migration barriers. |
| **Persistent Queue** | **SQLite-Backed Atomic Queue with Lease/Heartbeat** | Redis + Celery, RabbitMQ | Self-contained on Windows; atomic claim uses `BEGIN IMMEDIATE` and tested `UPDATE ... WHERE id=(SELECT ...) RETURNING`; leases require fencing and recovery logic. |
| **Worker Isolation** | **Subprocess HTTP REST + Shared Secret Token (`127.0.0.1`)** | Process stdio JSON, gRPC, Named Pipes | Complete crash isolation; authenticated loopback communication; process tree lifecycle managed by Windows Job Objects. |
| **Audio Processing** | **FFmpeg (Standalone Binary, LGPL compliant) + SoundFile** | Torchaudio, Librosa, PyDub | Robust format transcoding, channel mixing, and EBU R128 loudness normalization without Python GIL locks. |
| **Frontend Core** | **React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui** | Vue 3, Svelte 5, Qt/PySide6 | Industry standard for web-first SPAs; rich ecosystem for audio wave visualization; instant Vite HMR. |
| **Frontend State/Data** | **TanStack Query v5 + Zustand** | Redux Toolkit, Context API | Built-in caching, polling, automatic retries, and SSE reconnect handling for asynchronous AI jobs. |
| **Desktop Wrapper** | **Web-First (FastAPI Served) + Deferred Native Shell** | Tauri 2 (Immediate), Electron | Eliminates Rust toolchain blocker in Phase 1–4; runs in browser or Edge App; native packaging planned for Phase 5. |
| **Security & Auth** | **JWT (HS256) + Argon2id + Onboarding Wizard** | Hardcoded Localhost Admin, Basic Auth | Secure by design from Phase 1; eliminates accidental root localhost access; strict user ownership of audio and projects. |
| **Env Management** | **Per-Engine Isolated Virtual Envs (`python -m venv` / `uv`)** | Monolithic venv, Conda, Docker | Separates Python dependencies; it is not a process security sandbox and does not isolate the NVIDIA driver or Windows file permissions. |

---

## 2. Architecture Decision Records (ADRs)

### ADR-001: Backend Core Framework & Error Standards — FastAPI & RFC 9457
* **Context:** The application core requires high-performance async I/O, strict schema validation, and standardized error messaging for web clients, desktop wrappers, and future MCP agents.
* **Decision:** Use **FastAPI (Python 3.12)** with **Pydantic v2** for domain models and **RFC 9457 (Problem Details for HTTP APIs)** for all structured error responses.
* **Consequences:**
  * (+) Native OpenAPI 3.1 generation enables automated client SDK generation for TypeScript.
  * (+) RFC 9457 standardizes error fields (`type`, `title`, `status`, `detail`, `instance`, `invalid_params`).
  * (-) Developers must explicitly map internal domain exceptions to RFC 9457 response schemas.

---

### ADR-002: Desktop Client & Packaging Strategy — Web-First with Independent Lifecycle
* **Context:** The system must support single-user desktop use (Mode A) and multi-user LAN access (Mode B). The host machine currently lacks the Rust toolchain (`cargo`).
* **Decision:** 
  1. Build the UI as a **Web-First Single Page Application (React 19 + Vite)** served statically by FastAPI.
  2. For early local desktop usage, launch via a Windows shortcut invoking Edge App Mode (`msedge.exe --app=http://127.0.0.1:8765`), which runs in a chromeless, native-like window.
  3. The core server lifecycle is **completely decoupled** from the browser window: closing the UI does not terminate the background inference server.
  4. Packaging into a standalone installer (`.exe` via Inno Setup / WiX) or native wrapper (Tauri 2) is formally scheduled for Phase 5.
* **Consequences:**
  * (+) Zero development blockers regarding Rust/MSVC in Phases 1–4.
  * (+) 100% UI code parity between desktop and LAN browser users.
  * (-) In Phases 1–4, local launch requires a small launcher script (`launch-studio.bat` or Python tray process) rather than a single compiled `.exe`.

---

### ADR-003: Database Engine & Realistic PostgreSQL Migration Boundaries — SQLite WAL
* **Context:** The application needs relational persistence for users, projects, voices, audio artifacts, and job records on a single Windows host serving 1–20 concurrent LAN users.
* **Decision:** Use **SQLite 3 in WAL Mode** via **SQLAlchemy 2.0 (AsyncIO)** and **Alembic**.
* **Pragmatic PostgreSQL Migration Analysis (Disproving Naive Claims):**
  * *Correction in R1:* Migrating from SQLite to PostgreSQL is **NOT** merely changing a database connection string.
  * *Required adjustments if migrating in the future:*
    * SQLite uses dynamic typing; PostgreSQL enforces strict enum types and column lengths.
    * Concurrency locking differs: SQLite uses database-level locks, whereas PostgreSQL uses row-level locking (`SELECT FOR UPDATE SKIP LOCKED`).
    * Dialect-specific features: JSON operators (`->>`), UUID generation, and auto-increment sequences require distinct migration scripts.
  * *Justification for SQLite WAL today:* Up to 20 users generate far less than 50 write transactions per second. SQLite WAL easily handles thousands of read transactions and serialized writes without the operational overhead of installing a PostgreSQL service on Windows.

---

### ADR-004: Durable Job Queue — SQLite Atomic Leases & Worker Ownership
* **Context:** AI generation is long-running and GPU-constrained. Jobs must survive unexpected shutdowns, support retries with backoff, prevent duplicate execution, and allow clean cancellation.
* **Decision:** Implement a **Transactional Lease-Based Queue** directly inside the SQLite database.
* **Queue Operational Rules:**
  1. **Atomic Claiming:** Use the tested SQLite statement in `API_DATA_DESIGN.md`: `BEGIN IMMEDIATE`, `UPDATE jobs ... WHERE id=(SELECT id ... LIMIT 1) AND status='queued' RETURNING ...`. Do not assume `UPDATE ... LIMIT` support.
  2. **Worker Leases & Heartbeats:** Worker must refresh `lease_expires_at` every 5 seconds. If a worker dies, its lease expires, and the supervisor reclaims the job.
  3. **Idempotency & Deduplication:** Requests include an `idempotency_key`. Duplicate submissions return the existing job record without re-enqueuing.
  4. **Atomic Publication:** Rendered audio is written to a temporary scratch path, validated for format and size, and then moved atomically into the final artifact registry.
* **Consequences:**
  * (+) Persisted job records survive ordinary server restarts; individual attempts may need reconciliation, and artifact publication must be recovery-tested.
  * (+) Zero external daemon (Redis/RabbitMQ) required on Windows.

---

### ADR-005: Engine Worker Isolation & Lifecycle — Local HTTP with Shared Secret Token
* **Context:** Deep learning libraries (PyTorch CUDA, ONNX Runtime) have conflicting dependencies and can trigger uncatchable C++ segfaults or CUDA OOM aborts.
* **Decision:** Run each engine in a separate child process using its own virtualenv (`engines/<id>/.venv`), communicating via **HTTP/REST over loopback (`127.0.0.1:<ephemeral_port>`)**.
* **Security & Lifecycle Safeguards:**
  1. **Worker Authentication:** Core server generates a random cryptographic `AUTH_TOKEN` at startup and passes it to the worker via standard input or environment variable. Worker rejects all requests lacking `X-Worker-Token`.
  2. **Windows Process Tree Management:** Core server assigns worker processes to a **Win32 Job Object** (or monitors child PIDs) to ensure that if the core server terminates, all worker processes are forcibly terminated without leaving orphan background processes.
* **Consequences:**
  * (+) Process crash isolation: worker exceptions/segfaults generally do not terminate FastAPI; parent lifecycle and shared-driver failures still require testing.
  * (+) Clean binary audio streaming over standard HTTP multipart / WAV payloads.

---

### ADR-006: Audio DSP Pipeline & FFmpeg Distribution Compliance
* **Context:** The application must resample audio (24kHz to 48kHz), concatenate dialogue lines, insert silence pauses, and apply EBU R128 loudness normalization.
* **Decision:** Utilize an external static **FFmpeg binary** managed via Python `subprocess`, combined with `soundfile` and `numpy` for in-memory waveform analysis.
* **Licensing & Redistribution Strategy:**
  * For licensing review (do not claim compliance until exact FFmpeg build/configuration is audited):
    1. During development, developers use prebuilt FFmpeg binaries placed in `bin/ffmpeg.exe`.
    2. The application executes FFmpeg as an independent CLI tool (not linked into the Python application).
    3. Production installers must pin and audit a specific FFmpeg build and its `-version` configuration flags, determine LGPL/GPL obligations, and provide required notices/source or a documented external-install option. FFmpeg does not provide a single universal "official LGPL Windows binary".

---

### ADR-007: Security Foundation & Authentication Strategy (Introduced in Phase 1)
* **Context:** Security must be built into the core from day one, not bolted on in later phases. Localhost requests must not automatically receive unrestricted admin access.
* **Decision:** 
  1. Implement **Argon2id password hashing** and **JWT (HS256) session tokens** starting in Phase 1.
  2. **First-Run Onboarding Wizard:** On initial boot, if no users exist, the system enters an onboarding state forcing the creation of the primary Administrator account and generating a master recovery key.
  3. **Strict Resource Ownership:** Projects, custom cloned voices, and audio artifacts store an explicit `owner_id`. RBAC policies (Admin, Editor, Viewer) are checked on every API request.
* **Consequences:**
  * (+) Zero security debt when opening the system to LAN multi-user sharing.
  * (+) Prevents unauthorized manipulation of voice cloning data or job queues.

---

### ADR-008: Dynamic Resource-Aware Scheduling (Replacing Static VRAM Assumptions)
* **Context:** The RTX 3050 has 6GB nominal VRAM, but available VRAM fluctuates dynamically based on other Windows applications. Static assumptions (e.g. "3.8GB is always free") cause unexpected CUDA OOM crashes.
* **Decision:** Implement a **Dynamic Resource-Aware Scheduler**:
  1. **Telemetry:** Core server queries GPU memory dynamically using `pynvml` (NVIDIA Management Library) and system RAM using `psutil`.
  2. **Pre-Flight Admission:** Scheduler evaluates observed free VRAM against a **measured, versioned** per-model peak + safety margin; 2.8 GB is not an approved requirement and does not guarantee allocation success.
  3. **Graceful Hold & Backoff:** If VRAM or system RAM is insufficient, the job remains in `QUEUED` state with an explanatory status event, rather than crashing PyTorch.
  4. **Conservative CPU Concurrency:** Limit CPU-bound inference (VieNeu) to **1 concurrent job by default**, scaling up to 2 only if free system RAM exceeds 6GB.
