# AI Voice Studio — Phase 2 Release Gate R1 Verification Evidence

**Date:** 2026-10-08  
**Environment:** Windows 11, Intel Core i5-12400F, NVIDIA GeForce RTX 3050 6GB, 16GB RAM  
**Repository Branch:** `main`  
**Python Runtime:** Python 3.12.10 (Virtualenv `.venv`)  
**Node.js Runtime:** Node.js v22.14.0  

---

## 1. Full Pytest Suite Execution Evidence

**Command:**
```powershell
.venv\Scripts\pytest -v
```

**Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- D:\C\Dev\du an\TTS\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\C\Dev\du an\TTS
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 34 items

tests/contract/test_mock_engine.py::test_manifest_validation PASSED      [  2%]
tests/contract/test_mock_engine.py::test_mock_worker_lifecycle_and_contract PASSED [  5%]
tests/e2e/test_browser_e2e.py::test_real_browser_end_to_end_journey PASSED [  8%]
tests/integration/test_auth_api.py::test_auth_onboarding_lifecycle PASSED [ 11%]
tests/integration/test_durable_jobs.py::test_01_job_state_machine_valid_and_invalid_transitions PASSED [ 14%]
tests/integration/test_durable_jobs.py::test_02_atomic_claim_concurrency PASSED [ 17%]
tests/integration/test_durable_jobs.py::test_03_idempotency_payload_conflict PASSED [ 20%]
tests/integration/test_durable_jobs.py::test_04_lease_expiration_and_reclaiming PASSED [ 23%]
tests/integration/test_durable_jobs.py::test_05_fencing_token_rejection PASSED [ 26%]
tests/integration/test_durable_jobs.py::test_06_retry_with_exponential_backoff PASSED [ 29%]
tests/integration/test_durable_jobs.py::test_07_manual_retry_of_failed_job PASSED [ 32%]
tests/integration/test_durable_jobs.py::test_08_cancellation_queued_and_running PASSED [ 35%]
tests/integration/test_durable_jobs.py::test_09_server_restart_recovery PASSED [ 38%]
tests/integration/test_durable_jobs.py::test_10_resource_limits_and_waiting_reason PASSED [ 41%]
tests/integration/test_durable_jobs.py::test_11_sse_event_streaming_and_replay PASSED [ 44%]
tests/integration/test_durable_jobs.py::test_12_sse_strict_authorization_and_query_token_prohibition PASSED [ 47%]
tests/integration/test_durable_jobs.py::test_13_short_transactions_db_not_locked PASSED [ 50%]
tests/integration/test_durable_jobs.py::test_14_artifact_isolation_on_cancellation PASSED [ 52%]
tests/integration/test_jobs_api.py::test_tts_job_lifecycle_and_artifact PASSED [ 55%]
tests/integration/test_migrations.py::test_alembic_fresh_database_upgrade PASSED [ 58%]
tests/integration/test_migrations.py::test_alembic_upgrade_preexisting_db_without_data_loss PASSED [ 61%]
tests/integration/test_migrations.py::test_foreign_key_constraint_enforcement PASSED [ 64%]
tests/integration/test_migrations.py::test_sqlite_wal_mode_enabled PASSED [ 67%]
tests/integration/test_process_resilience.py::test_scenario_a_subprocess_kill_and_recovery PASSED [ 70%]
tests/integration/test_process_resilience.py::test_scenario_b_stale_worker_fencing_token_rejection PASSED [ 73%]
tests/integration/test_process_resilience.py::test_scenario_c_race_cancellation_vs_completion PASSED [ 76%]
tests/integration/test_process_resilience.py::test_scenario_d_multi_runner_cross_process_gpu_slot_enforcement PASSED [ 79%]
tests/integration/test_process_resilience.py::test_scenario_e_sse_stream_reconnection_and_replay PASSED [ 82%]
tests/integration/test_process_resilience.py::test_scenario_f_sqlite_online_backup_under_live_wal_writes PASSED [ 85%]
tests/integration/test_security_hardened.py::test_concurrent_onboarding_race_condition PASSED [ 88%]
tests/integration/test_security_hardened.py::test_bootstrap_token_ttl_expiration PASSED [ 91%]
tests/integration/test_security_hardened.py::test_multi_user_cross_authorization_isolation PASSED [ 94%]
tests/integration/test_spa_serving.py::test_spa_index_and_assets PASSED  [ 97%]
tests/integration/test_supervisor_resilience.py::test_worker_crash_isolation_and_restart PASSED [100%]

============================= 34 passed in 22.62s =============================
```

---

## 2. Safe SQLite Backup & Durability CLI Evidence

### 2.1 Audit of Existing Backups
**Command:**
```powershell
.venv\Scripts\python.exe -m apps.server.src.backup audit
```
**Output:**
```text
============================================================
 [AI VOICE STUDIO] AUDITING EXISTING DATABASE BACKUPS (3 found)
============================================================
 File:        studio.db (D:\AIVoiceStudioData\studio.db)
 Valid:       True
 Size:        86,016 bytes
 SHA256:      1708d18937f4e8cd71cdbb22ce9610018d82a1751447cb40b2b10c3ec41ef30a
 Integrity:   ok
 Alembic Rev: 20261008_0002
 Key Tables:  users=0, jobs=0, artifacts=0
------------------------------------------------------------
 File:        studio.db.phase1.bak (D:\AIVoiceStudioData\studio.db.phase1.bak)
 Valid:       True
 Size:        69,632 bytes
 SHA256:      e2460efe4eb95b38229e08775ee4f9901693a7245eff663de64279355351c479
 Integrity:   ok
 Alembic Rev: None
 Key Tables:  users=0, jobs=0, artifacts=0
------------------------------------------------------------
 File:        studio.db.phase1.bak (D:\AIVoiceStudioData\backups\studio.db.phase1.bak)
 Valid:       True
 Size:        69,632 bytes
 SHA256:      e2460efe4eb95b38229e08775ee4f9901693a7245eff663de64279355351c479
 Integrity:   ok
 Alembic Rev: None
 Key Tables:  users=0, jobs=0, artifacts=0
------------------------------------------------------------
============================================================
```

### 2.2 Live Online Backup Creation
**Command:**
```powershell
.venv\Scripts\python.exe -m apps.server.src.backup create
```
**Output:**
```text
============================================================
 [AI VOICE STUDIO] ONLINE BACKUP CREATED SUCCESSFULLY
============================================================
 Source:      D:\AIVoiceStudioData\studio.db
 Destination: D:\AIVoiceStudioData\backups\studio_20261008_090344.db
 Size:        86,016 bytes
 SHA256:      6948ebce9a12b82b22b2614859ddce83c32f21bbd0907729d93f9b08708f034c
 Integrity:   ok (Quick check: ok)
 Alembic Rev: 20261008_0002
 Tables:      {
  "users": 0,
  "engines": 1,
  "artifacts": 0,
  "jobs": 0,
  "alembic_version": 1,
  "job_events": 0
}
============================================================
```

### 2.3 Backup Integrity Verification
**Command:**
```powershell
.venv\Scripts\python.exe -m apps.server.src.backup verify D:\AIVoiceStudioData\backups\studio_20261008_090344.db
```
**Output:**
```text
============================================================
 [AI VOICE STUDIO] BACKUP VERIFICATION REPORT
============================================================
 Path:        D:\AIVoiceStudioData\backups\studio_20261008_090344.db
 Valid:       True
 Size:        86,016 bytes
 SHA256:      6948ebce9a12b82b22b2614859ddce83c32f21bbd0907729d93f9b08708f034c
 Integrity:   ok
 Quick check: ok
 Alembic Rev: 20261008_0002
 Tables & Row Counts:
   - users               : 0 rows
   - engines             : 1 rows
   - artifacts           : 0 rows
   - jobs                : 0 rows
   - alembic_version     : 1 rows
   - job_events          : 0 rows
============================================================
```

---

## 3. Frontend Production Build Evidence

**Command:**
```powershell
npm run build (in apps/web)
```
**Output:**
```text
> ai-voice-studio-web@1.0.0 build
> tsc && vite build

vite v6.4.4 building for production...
transforming...
✓ 1600 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.61 kB │ gzip:  0.40 kB
dist/assets/index-CQXdZm4X.css   25.03 kB │ gzip:  5.13 kB
dist/assets/index-B51LBRZf.js   283.67 kB │ gzip: 83.38 kB
✓ built in 2.48s
```
