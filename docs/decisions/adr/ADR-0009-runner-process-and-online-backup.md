---
id: ADR-0009
title: Decoupled Standalone Runner Process & SQLite Online Backup API
status: proposed
decision_authority: Product Owner
owner: Principal Backend Engineer
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0009: Decoupled Standalone Runner Process & SQLite Online Backup API

## Context
In Phase 1 and Phase 2, the `DurableJobScheduler` was run inside the FastAPI application lifespan (`embedded` mode). While convenient for zero-config single-process development, this coupling has limitations:
1. Long-running synthesis worker supervision shares the FastAPI OS process lifecycle.
2. Web server restarts or reloads terminate all executing inference jobs unless decoupled.
3. In multi-tenant or headless deployments, scaling or isolating the API server from compute-heavy worker orchestration requires running the scheduler in a dedicated process.
4. SQLite WAL mode requires transactionally consistent live backups without locking or tearing database files during active writes.

## Decision Proposed
1. **Dual Scheduler Deployment Modes**:
   - **Embedded Mode (Default: `STUDIO_EMBEDDED_SCHEDULER=true`)**: The scheduler and worker supervisor run inside the FastAPI server lifespan for developer ergonomics and desktop single-binary packaging.
   - **Standalone Mode (`STUDIO_EMBEDDED_SCHEDULER=false`)**: The FastAPI server operates purely as an API gateway and job persistence layer. A dedicated OS process (`python -m apps.server.src.runner`) executes the `DurableJobScheduler`, discovers engines, supervises worker subprocesses via Windows Job Objects, and claims jobs using database-backed leases.
2. **Database-Backed Multi-Process Concurrency Limits**:
   - Hardware slots (max 1 GPU, max 1 CPU) are enforced directly against live unexpired leases in the SQLite database (`jobs` table with `lease_expires_at > now()`). This guarantees strict hardware limits even when multiple runner processes or threads poll concurrently.
3. **Safe SQLite Online Backup API**:
   - All backups must use `sqlite3.Connection.backup()` (the official SQLite Online Backup API), step-by-step with `pages=100`, rather than direct OS file copying.
   - Pre-restore and post-backup integrity validation via `PRAGMA integrity_check` and table inventory counting is mandatory. Automatic safety snapshots are created prior to live restore operations.

## Trade-offs & Alternatives Considered
- **Celery / Redis / RabbitMQ**: High external dependency overhead on Windows; excessive complexity for single-node workstation deployment.
- **Embedded Only**: High risk of job interruption during web server restarts; impossible to isolate API worker from compute faults.
- **OS File Copying (`shutil.copy2`)**: Risks capturing corrupt or torn WAL database pages if writes occur concurrently. SQLite Online Backup API is atomic and locks pages safely without blocking reads.

## Validation & Evidence
- Automated process resilience test suite (`tests/integration/test_process_resilience.py`):
  - Scenario A: Subprocess kill and stranded job recovery.
  - Scenario B: Stale worker completion rejection across separate processes via fencing tokens.
  - Scenario C: Race cancellation vs completion with zero orphan artifacts.
  - Scenario D: Two separate runner instances strictly respecting the 1-GPU hardware slot limit.
  - Scenario E: SSE stream reconnection and monotonic event replay.
  - Scenario F: SQLite online backup and restore during high-frequency concurrent WAL writes.
- Passed 34/34 test suites in 22.6s.

## Status and Links
- **Status:** Proposed (Awaiting Product Owner Approval).
- **Related ADRs:** [ADR-0001](ADR-0001-api-first-modular-monolith.md), [ADR-0003](ADR-0003-sqlite-queue.md), [ADR-0004](ADR-0004-worker-isolation.md), [ADR-0006](ADR-0006-data-boundaries.md).
