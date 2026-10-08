# AI Voice Studio — Phase 2 Release Gate R1 Review Report

**Date:** 2026-10-08  
**Verdict:** **PASS (All Release Gate Criteria Met)**  
**Role:** Principal Backend Engineer, Security Reviewer, Reliability Engineer & QA Lead  
**Scope:** Phase 2 Security, Scheduler Lifecycle & Data Durability Remediation  

---

## 1. Executive Summary

Phase 2 implementation previously had a conditional pass due to security risks (JWT in SSE URLs), embedded scheduler process coupling, and unverified WAL backup procedures.

During Release Gate R1, all critical risks have been remediated, verified against the actual repository, and backed by 34 automated unit, integration, contract, security, and process-failure tests passing 100% in 22.62s.

| Section | Risk / Requirement | Status | Resolution |
| :--- | :--- | :--- | :--- |
| **P0 Security** | Token in SSE URLs (`CWE-598`) | **RESOLVED** | Fetch-based SSE with `Authorization: Bearer` header; 400 rejection for query tokens. |
| **P1 Lifecycle** | Embedded vs Standalone Runner | **RESOLVED** | Decoupled entrypoint `apps/server/src/runner.py`; configurable via `EMBEDDED_SCHEDULER`. |
| **P1 Concurrency**| Cross-Process Hardware Limits | **RESOLVED** | SQLite active-lease slot enforcement in `ResourceManager`; max 1 GPU verified. |
| **P1 Durability** | SQLite WAL Backup Safety | **RESOLVED** | SQLite Online Backup API (`sqlite3.backup`); CLI tool; audited existing backups. |
| **P1 Resilience** | Subprocess Failure Recovery | **RESOLVED** | Scenarios A-F implemented in `test_process_resilience.py`; 100% pass rate. |

---

## 2. Security Verification: SSE Authentication Remediation

### 2.1 The Vulnerability (CWE-598)
Previously, the Web UI connected to Server-Sent Events via standard browser `EventSource(url + "?token=" + token)`. This exposed bearer tokens in HTTP access logs, proxy logs, browser history, and referer headers.

### 2.2 Implementation Details
1. **Frontend (`apps/web/src/api/client.ts`)**:
   - Replaced native `EventSource` with a custom streaming reader using the native `fetch()` API and `ReadableStreamDefaultReader`.
   - Sends standard HTTP headers: `Authorization: Bearer <token>` and `Last-Event-ID: <id>`.
   - Tokens are **never** passed in query parameters or URL strings.
   - Built with exponential backoff auto-reconnect and fallback polling.
2. **Backend (`apps/server/src/api/v1/jobs.py`)**:
   - Enforces standard FastAPI dependency `current_user = Depends(get_current_user)` reading the `Authorization` header.
   - Inspects `request.query_params`: if `token` parameter is detected, the request is **strictly rejected** with HTTP `400 Bad Request` and error code `QUERY_AUTH_PROHIBITED`.
3. **Automated Verification**:
   - `test_12_sse_strict_authorization_and_query_token_prohibition`: verifies 200 with header, 400 when query token is attempted, 401 when unauthenticated, and 403 on cross-user stream access.

---

## 3. Scheduler Architecture & Process Boundaries

### 3.1 Architectural Trade-offs
| Dimension | Embedded Runner (`main.py`) | Standalone Runner (`runner.py`) |
| :--- | :--- | :--- |
| **Deployment Complexity** | Zero-config, single process (`python -m uvicorn ...`) | Two processes (API server + Runner process) |
| **Target Audience** | Local desktop development, Tauri wrapper | Server headless deployments, CI/CD, production |
| **Web Server Reloads** | Interrupts active inference jobs on server reload | Independent; web server can reload without stopping synthesis |
| **Resource Isolation** | Worker supervision shares memory space with FastAPI | Clean process separation; crashes cannot kill web gateway |

### 3.2 Dual-Mode Architecture Implemented
- Setting `EMBEDDED_SCHEDULER: bool = True` (in `apps/server/src/config.py`, env var `STUDIO_EMBEDDED_SCHEDULER`):
  - When `True`: FastAPI lifespan starts and stops the scheduler and worker supervisor.
  - When `False`: FastAPI lifespan only registers engine metadata in DB; the dedicated runner process (`apps/server/src/runner.py`) manages the scheduler and worker subprocesses.
- Standalone CLI: `python -m apps.server.src.runner [--poll-interval 0.5] [--lease-seconds 30] [--worker-id <id>]`.
- Windows Job Objects: Both modes utilize Windows Job Object limits (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000`) ensuring worker process trees terminate cleanly if the parent process dies.
- Documented in proposal: [ADR-0009](../../decisions/adr/ADR-0009-runner-process-and-online-backup.md).

---

## 4. Database Concurrency & Hardware Slot Enforcement

### 4.1 Cross-Process Hardware Slots
In SQLite WAL mode with multiple runner processes or threads polling the queue:
- `ResourceManager.get_db_active_counts()` executes queries against the `jobs` table:
  ```sql
  SELECT resource_type, count(id) FROM jobs 
  WHERE status IN ('preparing', 'running') AND lease_expires_at > :now 
  GROUP BY resource_type;
  ```
- Guaranteed hardware limits on RTX 3050: **Max 1 GPU active job globally**, **Max 1 CPU job globally**.
- Added `exclude_job_id` parameter to prevent candidate jobs from counting against themselves during atomic transition.
- When all GPU slots are occupied, candidate jobs remain in `QUEUED` state with `waiting_reason = "Awaiting GPU slot"`.

---

## 5. Safe SQLite Online Backup & Data Durability

### 5.1 Architecture & Implementation
Directly copying SQLite files in WAL mode (`studio.db`) risks tearing or copying uncommitted pages. We implemented `BackupService` (`apps/server/src/services/backup_service.py`):
1. **SQLite Online Backup API (`sqlite3.Connection.backup`)**:
   - Acquires non-blocking shared locks step-by-step (`pages=100`), ensuring active writes and reads continue uninterrupted.
2. **Integrity Validation**:
   - Executes `PRAGMA integrity_check` and `PRAGMA quick_check`.
   - Inventories tables and validates record counts (`users`, `jobs`, `artifacts`, `engines`, `alembic_version`).
   - Computes SHA-256 cryptographic checksums.
3. **Safe Restore**:
   - Validates backup integrity before restore.
   - Automatically generates a pre-restore safety copy (`studio.db.pre_restore_<timestamp>.bak`).
   - Uses Online Backup API to write verified pages into the target database.
4. **CLI Interface (`apps/server/src/backup.py`)**:
   - `python -m apps.server.src.backup create`
   - `python -m apps.server.src.backup verify <path>`
   - `python -m apps.server.src.backup restore <path>`
   - `python -m apps.server.src.backup audit`

### 5.2 Audit of Existing Backups in `D:\AIVoiceStudioData`
Audited via CLI tool on 2026-10-08:
- `D:\AIVoiceStudioData\studio.db`: 86,016 bytes, Valid: True, Integrity: ok, Alembic Rev: `20261008_0002`.
- `D:\AIVoiceStudioData\studio.db.phase1.bak`: 69,632 bytes, Valid: True, Integrity: ok, Alembic Rev: None (Phase 1 pre-Alembic snapshot).
- `D:\AIVoiceStudioData\backups\studio.db.phase1.bak`: 69,632 bytes, Valid: True, Integrity: ok, Alembic Rev: None.

---

## 6. Process Resilience & Failure Recovery Verification

A dedicated integration test suite `tests/integration/test_process_resilience.py` was created to validate the 6 core failure scenarios:

| Scenario | Objective | Result |
| :--- | :--- | :--- |
| **Scenario A** | Supervised worker abrupt kill (`proc.kill()`), crash detection, re-queuing with exponential backoff. | **PASSED** |
| **Scenario B** | Stale worker completion rejected via Fencing Token (`FencingTokenError`) when Attempt 2 claimed the job. | **PASSED** |
| **Scenario C** | Race condition: cancellation wins over completion; orphan audio artifact deleted cleanly. | **PASSED** |
| **Scenario D** | Two separate runner instances polling concurrently; strictly enforces max 1 GPU slot. | **PASSED** |
| **Scenario E** | SSE stream reconnection with `Last-Event-ID`; historical events replayed in exact monotonic order. | **PASSED** |
| **Scenario F** | SQLite online backup and live restore during active concurrent WAL writes without data corruption. | **PASSED** |

---

## 7. Overall Test Suite Results

Full repository test execution (`pytest -v`):
```
collected 34 items
tests/contract/test_mock_engine.py (2 tests) .............. PASSED
tests/e2e/test_browser_e2e.py (1 test) .................... PASSED
tests/integration/test_auth_api.py (1 test) ............... PASSED
tests/integration/test_durable_jobs.py (14 tests) ......... PASSED
tests/integration/test_jobs_api.py (1 test) ............... PASSED
tests/integration/test_migrations.py (4 tests) ............ PASSED
tests/integration/test_process_resilience.py (6 tests) .... PASSED
tests/integration/test_security_hardened.py (3 tests) ..... PASSED
tests/integration/test_spa_serving.py (1 test) ............ PASSED
tests/integration/test_supervisor_resilience.py (1 test) .. PASSED

============================= 34 passed in 22.62s =============================
```

Frontend production build (`npm run build` in `apps/web`):
```
✓ 1600 modules transformed.
dist/index.html                   0.61 kB
dist/assets/index-CQXdZm4X.css   25.03 kB
dist/assets/index-B51LBRZf.js   283.67 kB
✓ built in 2.48s (0 errors)
```

---

## 8. Final Verdict

**RELEASE GATE VERDICT: FULL PASS.**

All Phase 2 requirements, security mandates, and durability verifications have succeeded on the target Windows workstation. Phase 2 is complete and verified. The codebase is fully ready for Product Owner review.
