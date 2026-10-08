# AI Voice Studio — Phase 2 Release Gate R1 Remediation Changelog

**Date:** 2026-10-08  
**Scope:** Phase 2 Security, Lifecycle & Durability Remediation  

---

## 1. Summary of Changes

This changelog records the complete remediation performed during Phase 2 Release Gate R1.

### 1.1 Security Hardening
- **Frontend Fetch-based SSE Client (`apps/web/src/api/client.ts`)**:
  - Replaced native browser `EventSource` with custom streaming reader via native `fetch()` and `ReadableStreamDefaultReader`.
  - Injected `Authorization: Bearer ${this.token}` and `Last-Event-ID: ${lastEventId}` standard HTTP headers.
  - Eliminated token query string leakage (`CWE-598`).
  - Implemented exponential backoff auto-reconnection and polling fallback.
- **Backend SSE Strict Endpoint (`apps/server/src/api/v1/jobs.py`)**:
  - Enforced `current_user = Depends(get_current_user)` reading `Authorization` header.
  - Added query param inspection: rejects `?token=...` with `400 Bad Request` (`QUERY_AUTH_PROHIBITED`).
  - Preserved `Last-Event-ID` parsing and user ownership verification (403 for unauthorized subscribers).

### 1.2 Standalone Runner Architecture & Concurrency
- **Configuration Toggle (`apps/server/src/config.py`)**:
  - Added `EMBEDDED_SCHEDULER: bool = True` (configurable via `STUDIO_EMBEDDED_SCHEDULER`).
- **FastAPI Lifespan Decoupling (`apps/server/src/main.py`)**:
  - Conditionally starts/stops the scheduler and spawns workers based on `settings.EMBEDDED_SCHEDULER`.
- **Standalone Runner Entrypoint (`apps/server/src/runner.py`)**:
  - Created standalone process runner (`python -m apps.server.src.runner`).
  - Supports `--poll-interval`, `--lease-seconds`, `--worker-id` CLI flags.
  - Handles graceful OS signal termination (`SIGINT`, `SIGTERM`), draining tasks and stopping child workers.
- **Database-Backed Resource Slot Enforcement (`apps/server/src/services/resource_manager.py`)**:
  - Enforces max 1 GPU / max 1 CPU slots across processes by querying active SQLite leases (`status IN ('preparing', 'running') AND lease_expires_at > now()`).
  - Added `exclude_job_id` parameter to avoid self-counting deadlocks during atomic claim transitions.

### 1.3 Safe SQLite Online Backup & Data Durability
- **Online Backup Service (`apps/server/src/services/backup_service.py`)**:
  - Uses `sqlite3.Connection.backup()` step-by-step (`pages=100`) for non-blocking WAL database backups.
  - Automates integrity verification (`PRAGMA integrity_check`, `PRAGMA quick_check`, table row counting).
  - Implements safe live restore with automatic pre-restore safety copies.
- **Backup CLI (`apps/server/src/backup.py`)**:
  - Provides `create`, `verify`, `restore`, and `audit` subcommands.
- **Artifact Deletion (`apps/server/src/services/artifact_service.py`)**:
  - Added `delete_artifact()` to remove database records and disk audio files on cancellation races.

### 1.4 Verification & Resilience Testing
- **Process Failure Test Suite (`tests/integration/test_process_resilience.py`)**:
  - Scenario A: Subprocess kill and stranded job recovery.
  - Scenario B: Stale worker completion rejection via fencing token.
  - Scenario C: Race cancellation vs completion with orphan artifact cleanup.
  - Scenario D: Multi-runner cross-process GPU slot limit enforcement.
  - Scenario E: SSE reconnection and monotonic event replay.
  - Scenario F: SQLite online backup under live concurrent WAL writes.
- **Regression Updates (`tests/integration/test_durable_jobs.py`)**:
  - Updated `test_12` to use `async with client.stream(...)` to avoid hanging indefinitely on open SSE responses.
  - Isolated manual tests from background daemon races.

---

## 2. File Change Inventory

| File Path | Action | Description |
| :--- | :--- | :--- |
| `apps/server/src/api/v1/jobs.py` | Modified | SSE auth via Authorization header, 400 rejection for `?token=`. |
| `apps/server/src/config.py` | Modified | Added `EMBEDDED_SCHEDULER: bool = True`. |
| `apps/server/src/main.py` | Modified | Lifespan checks `EMBEDDED_SCHEDULER`. |
| `apps/server/src/runner.py` | Created | Dedicated standalone runner entrypoint. |
| `apps/server/src/services/artifact_service.py` | Modified | Added `delete_artifact()` helper. |
| `apps/server/src/services/backup_service.py` | Created | Safe SQLite Online Backup & restore service. |
| `apps/server/src/backup.py` | Created | CLI tool for backup create/verify/restore/audit. |
| `apps/server/src/services/durable_queue_service.py` | Modified | Integrated DB-backed resource manager with `exclude_job_id`. |
| `apps/server/src/services/engine_service.py` | Modified | Added `spawn_workers` param to `discover_and_register_engines`. |
| `apps/server/src/services/resource_manager.py` | Modified | Added database active lease counts and `exclude_job_id`. |
| `apps/server/src/supervisor/scheduler.py` | Modified | Bound `_wake_event` on `start()`, unique `worker_id` per process. |
| `apps/web/src/api/client.ts` | Modified | Custom fetch-based SSE reader with Authorization header. |
| `apps/web/dist/*` | Rebuilt | Production web bundle regenerated. |
| `tests/integration/test_durable_jobs.py` | Modified | Streaming test update, isolated scheduler in manual tests. |
| `tests/integration/test_process_resilience.py` | Created | Scenarios A-F failure resilience test suite. |
| `docs/decisions/adr/ADR-0009-runner-process-and-online-backup.md` | Created | Proposed ADR for standalone runner & online backup. |
| `docs/reports/reviews/PHASE_02_RELEASE_GATE_REVIEW.md` | Created | Release Gate R1 review report. |
| `docs/reports/tests/PHASE_02_RELEASE_GATE_EVIDENCE.md` | Created | Test run and CLI evidence logs. |
| `docs/reports/phases/PHASE_02_REMEDIATION_CHANGELOG.md` | Created | This remediation changelog. |
