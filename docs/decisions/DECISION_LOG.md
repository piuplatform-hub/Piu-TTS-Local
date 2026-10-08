# Decision register

**Last updated:** 2026-10-08 · **Approval state:** All decisions proposed; Product Owner has not yet authorized Phase 1.

| ADR | Subject | Status | Proposed choice | Next gate |
|---|---|---|---|---|
| [0001](adr/ADR-0001-api-first-modular-monolith.md) | Headless core & module boundaries | proposed | API-first modular monolith | DOC |
| [0002](adr/ADR-0002-web-first-ui.md) | Web-first UI and optional native wrapper | proposed | React/Vite now; Tauri later if justified | DOC |
| [0003](adr/ADR-0003-sqlite-queue.md) | SQLite and reliable queue | proposed | WAL + fenced leases (Phase 2) | DOC / PH1 |
| [0004](adr/ADR-0004-worker-isolation.md) | Engine workers | proposed | Per-engine runtime + loopback worker process | DOC |
| [0005](adr/ADR-0005-first-run-security.md) | Bootstrap & authorization | proposed | One-time local setup secret + atomic bootstrap | DOC / PH1 |
| [0006](adr/ADR-0006-data-boundaries.md) | Data storage and backup | proposed | Configurable persistent data root; restore evidence | DOC |
| [0007](adr/ADR-0007-plugin-capabilities.md) | Plugin SDK and trust | proposed | Capability manifest, vetted package, contract tests | DOC |
| [0008](adr/ADR-0008-mcp-readiness.md) | Future MCP | proposed | Extension point only, independently authorized later | DOC |

**How to approve:** Change status in each ADR to `accepted`, add approval date and authorized person, then update register and roadmap. Do not make Gemini's self-assessment an approval.
