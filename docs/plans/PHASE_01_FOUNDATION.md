---
id: PLAN-PH1-001
title: Phase 1 foundation, mock speech vertical slice
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# Phase 1 — Foundation, security, Mock Engine, Web UI

**Authorization:** NOT GRANTED. This document is a candidate implementation plan; no model downloads authorized.

## In scope
- Audit existing workspace and git worktree; create monorepo only after a safe diff/backup plan.
- FastAPI, Pydantic, Python dependency lock, SQLite/Alembic initial migrations.
- Secure first-run admin onboarding (local, one-time setup credential, atomic bootstrap) and basic RBAC/ownership checks.
- Versioned Engine SDK/manifest validation and authenticated loopback Mock Engine producing **non-speech WAV** (sine/noise) only.
- React/Vite app shell, login/onboarding, project-neutral speech form, generated OpenAPI TS client, status/progress, WAV preview/download.
- Localhost-only start/stop scripts and documentation; log health and errors with redaction.

## Out of scope
No actual VieNeu/Qwen packages or weights; no CUDA install, LAN ports/firewall/TLS, Windows services, MCP, production packaged installer, full durable leases or silent rollout to coworkers.

## Acceptance and verification (all unchecked until actually tested)
- [ ] Browser → bootstrap → login → enter text → select Mock → submit → observe job → play/download **valid mock WAV**.
- [ ] Concurrent initial Admin bootstrap attempts yield **exactly one** setup success; access denied with incorrect setup secret.
- [ ] Unauthorized user cannot read another user's audio artifact/project/voice profile.
- [ ] Independent mock-worker process crash does not terminate FastAPI; error visible in UI.
- [ ] OpenAPI-generated TS client typechecks; API paths consistent.
- [ ] `pytest` contract/integration suite, frontend typecheck/build and a reproduction script report exact commands and outcomes.
- [ ] Git status and commit hash recorded; no external model downloads; all changes under approved directories.

## Gate after Phase 1
Publish `reports/reviews/YYYY-MM-DD-phase1-implementation.md` with evidence, list unresolved defects and obtain owner acceptance. **Phase 1B is separately approved** and must not start automatically.

## Rollback
Keep source changes version-controlled and confined to the approved workspace. No overwrite of existing data; migrations require reversible/backup-first procedure. Mock data may be rebuilt only with explicit permission.
