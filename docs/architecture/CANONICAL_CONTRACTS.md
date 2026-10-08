# Canonical architecture contracts — R1.1

**Status:** Proposed — awaiting owner approval · **Date:** 2026-10-08 · **Scope:** design only

## Purpose and precedence
This page resolves contradictions inherited from Gemini R1. `docs/architecture/*` remain the full design record; this page is the **proposed canonical interface/semantics** pending owner approval. Once approved, accepted ADRs, this contract, and OpenAPI generated from running code must be kept consistent; unapproved plans are not implementation facts.

## Architecture invariants
- API-first Headless Core (application services independent of FastAPI request and GUI frameworks).
- Web-first React/Vite UI; desktop window may wrap the same client later. Desktop wrapper is not a privileged inference process.
- Modular monolith + isolated subprocess inference workers; isolated `.venv` does not imply OS sandboxing.
- Multiple LAN users send asynchronous jobs; **no** LAN listener until owner approves deployment security.
- Engine registry ≠ model registry ≠ voice profiles ≠ runtime installations; capabilities are discovered and schema validated.

## Canonical API paths (proposed v1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Limited health; never expose credentials or sensitive metrics publicly |
| GET | `/api/v1/auth/status` | First-run status without disclosing secrets |
| POST | `/api/v1/auth/onboard` | One-time local bootstrap with protected setup token |
| POST | `/api/v1/auth/login` | Login/session issuance |
| GET | `/api/v1/auth/me` | Current principal and granted permissions |
| GET | `/api/v1/engines` | Approved/visible engine metadata and capabilities |
| GET | `/api/v1/voices` | Authorized voices only |
| POST | `/api/v1/jobs/speech` | Submit TTS; returns `202`, job resource URL |
| POST | `/api/v1/jobs/clone` | Submit cloning with authorized reference |
| GET | `/api/v1/jobs/{job_id}` | Authoritative job state |
| POST | `/api/v1/jobs/{job_id}/cancel` | Request cancellation |
| GET | `/api/v1/jobs/{job_id}/events` | SSE events; replay requires persisted log |
| GET | `/api/v1/artifacts/{artifact_id}` | Authorized audio retrieval |
| GET, POST | `/api/v1/projects` | Project list/create; all mutations authorized |

The alternate `/api/v1/speech/jobs` path is **not** canonical. Source OpenAPI is authoritative once implemented; generated TS clients are produced from it and drift-tested. Errors use RFC 9457 `application/problem+json` at HTTP boundary.

## First-run bootstrap safety
- Bootstrap is restricted to loopback and a one-time setup credential delivered out of band (local launcher/console); never expose setup token from `/auth/status`.
- Transactionally guard unique first-admin creation (singleton row/unique constraint + `BEGIN IMMEDIATE`), so concurrent requests cannot install two admins.
- Disable the bootstrap credential immediately after success. Do not persist plaintext secrets. Recovery is a separate documented feature with tests.
- RBAC/ownership checks live in application services, including per-artifact and voice-sample access.

## Job semantics (R1.1 proposed)
- In Phase 1 a **development-only** single-process dispatcher is acceptable for one complete Mock Engine vertical slice. **Do not** describe it as durable.
- Phase 2 introduces SQLite transactional claiming, leases, fencing `attempt_id + lease_generation`, heartbeat and stale-worker reconciliation. Never directly reclaim an expired RUNNING attempt in the normal QUEUED claim statement.
- Jobs are **at-least-once attempts**, not guaranteed exactly-once synthesis. Idempotency is scoped to `(principal, idempotency_key)` and checked against canonical request payload hash.
- Artifacts are first generated in staging; validate, checksum, atomic-rename on the same volume, then commit DB pointer. Reconciliation handles potential file/DB crash gap.
- SSE replay requires persisted event sequence; otherwise document reconnect → re-GET state behavior.

## Workers and plugin trust
- One engine per independently managed process/virtual environment, HTTP loopback only, ephemeral port, per-launch secret; lifecycle monitored by supervisor.
- Manifest/API declares verified capabilities only; optional `clone`, `cancel`, `load`, `unload`, streaming. Unsupported features produce a structured error.
- Checksum establishes integrity compared with a trusted reference, not code authenticity; no automatic installation/execution of new GitHub repos. Approval and vetted source/commit/locked dependencies are mandatory.
- Worker processes are **not** security-isolated by localhost or `.venv`; operator account privileges/ACLs remain important.

## Data, Windows, operations and licensing
- `STUDIO_DATA_DIR` is configurable. `D:\AIVoiceStudioData` is a proposed *custom* location; verify before writing. Local default per-user could be `%LOCALAPPDATA%\AI Voice Studio` and service data requires an ACL-approved dedicated location.
- Backups encompass SQLite plus media assets with a consistent manifest, and a tested restore. Storage never resides solely under application binaries.
- Dynamic GPU telemetry is advisory; it cannot reserve VRAM against CapCut/other Windows apps. All peak RAM/VRAM and RTF values remain **unverified** until Phase 1B.
- Review legal obligations for **exact** upstream code, weight model and FFmpeg binary/version/configuration before any redistribution.
- MCP is deferred. Design reference: [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports) — Streamable HTTP is per-request POST/JSON or POST/SSE, without the legacy GET event stream.

## Phase gates
1. **DOC:** Approve documentary baseline and repository docs governance.
2. **PH1:** Explicit permission to edit code/install local development dependencies and run localhost-only mock pipeline.
3. **SPIKE:** Separate permission to clone upstream repo, install ML runtimes and download model weights/run GPU tests.
4. **LAN:** Explicit permission for network/firewall/TLS/client rollout.
5. **RELEASE:** Security/license/backup review.

**Evidence rule:** All tables describing expected behavior are *acceptance criteria*, not tests already passed.
