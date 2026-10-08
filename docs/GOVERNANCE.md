# Documentation governance

**Status:** Accepted (2026-10-08 by Product Owner) · **Owner:** Product Owner + Technical Lead · **Created:** 2026-10-08

## Document lifecycle

`draft` → `proposed` → `accepted` → `superseded` or `rejected`. Only the Product Owner can authorize development phases and network/model changes. An ADR marked `accepted` must include date and decision authority. Gemini/AI can propose but never self-approve its own architecture by writing "Approved".

Metadata header for new documents:

```yaml
---
id: PLAN-YYYYMMDD-001
title: Short meaningful title
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
related: [ADR-0001]
---
```

Existing 9 R1 docs retain their original title style; R1.1 status is visibly marked at top to avoid destructive rewrites. Use a document type stable ID for future files.

## Naming conventions

- ADR: `decisions/adr/ADR-0001-title.md`; numbers monotonic, **never reuse**.
- Plans: `plans/YYYY-MM-DD-short-title.md` (special stable phase plan `PHASE_01_FOUNDATION.md` allowed).
- Reports: `reports/reviews/YYYY-MM-DD-subject.md` or `reports/benchmarks/YYYY-MM-DD-model.md`.
- Ideas: `ideas/YYYY-MM-DD-topic.md` with intake index in `ideas/README.md`.
- Specs/contracts: uppercase stable identifiers or `snake_case.md`, version each breaking change.
- Files are UTF-8, relative Markdown links, Mermaid fenced diagrams, no embedded secrets or personal access tokens.

## Writing and review rules

- Distinguish **Observed**, **Source-derived**, **Assumption**, **Proposal**, **Tested**.
- Source-derived statements carry upstream URL and retrieval date in `research/SOURCE_REGISTER.md` when version-sensitive.
- Any API path/parameter modification updates canonical contract, OpenAPI/SDK plan, tests, and ADR where architecture changes.
- Any dependency/model choice records exact repo, revision/hash, code-vs-weights licensing, benchmark data and compatibility status.
- Plans specify scope, out-of-scope, DoD and rollback; reports provide evidence and limitations, no unchecked `[x]` on unexecuted tasks.
- Review link integrity and inconsistent paths/statuses before closing a phase.
- A generated docs bundle is an **external proposal** until reviewed/merged into the live PC git repo; check diffs and never blindly overwrite current work.

## Approval checkpoints

| Gate | What approval permits | What it does not permit |
|---|---|---|
| DOC | Accept documentation baseline and docs directory | Edit app code, install runtimes, download models |
| PH1 | Build mocked localhost product foundation | Install real TTS weights, LAN exposure |
| SPIKE | Controlled approved engine installs, isolated ML benchmarks | Unapproved production deployment |
| LAN | Hardened LAN deployment with TLS and per-user controls | Internet exposure by default |
| RELEASE | Package and share after license/security/restore evidence | Unreviewed plugins automatically executing |

## Retention, confidentiality, and backups

Public code documents should avoid embedding usernames, tokens, raw voice sample data, private LAN IPs, or user file contents. Architecture review and phase reports can be committed; sensitive logs/videos/audio should be excluded from Git and referenced via safe storage. Archive historical architecture snapshots rather than deleting them. Include `docs/` in version control and normal repo backups.
