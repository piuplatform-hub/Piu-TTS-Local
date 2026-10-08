---
id: REVIEW-20261008-001
title: R1.1 documentation reconciliation report
status: proposed
owner: Technical Lead
created: 2026-10-08
updated: 2026-10-08
---

# R1.1 document review — 2026-10-08

## Scope and evidence
Reviewed 9 uploaded Gemini R1 Markdown documents and revised copies. Preserved the exact R1 source documents under `docs/archive/r1-original/`. External official references are registered in `docs/research/SOURCE_REGISTER.md`.

## Key changes
- Canonical REST path `/api/v1/jobs/speech`; source OpenAPI to be generated from real implementation later.
- SQLite claims only QUEUED jobs; expired active jobs require a separate supervisor recovery path and attempt fencing.
- First admin is not claimed simply because user count is zero; protect bootstrap with one-time local secret and transaction.
- Plugin hash is not a digital signature; manifest example invalid for production until approved pin/version/hash.
- Phase 1 includes true Mock Engine UI→audio slice; queue durability belongs Phase 2.
- MCP 2026-07-28 design reference, no implementation; FFmpeg exact-build compliance review mandatory.
- Configurable data root, database+asset backup design, no hardcoded user-specific install paths.

## Scope-limited SQL syntax check
One SQLite sanity check was performed in an isolated container (SQLite 3.46.1): a queued job was claimed once, then a second sequential claim returned zero rows. This is **not** a Windows, concurrent-worker, crash-recovery, or production acceptance test.

## Outcome
**Documentation baseline R1.1: PROPOSED, NOT APPROVED.** Nothing was installed, executed or benchmarked on the user's Windows PC as part of this package generation. Next step: Antigravity safely merge into actual workspace after owner review and record commit/diff. The original Gemini Phase 0 inspection data remains reported-only and is not re-verified by this report.

## Open risks
See [Open Decisions](../../architecture/OPEN_DECISIONS.md) and [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md). All implementation deliverables remain future acceptance criteria.
