# Decision register

**Last updated:** 2026-10-08 · **Approval state:** All 8 ADRs accepted by Product Owner as baseline architectural direction (2026-10-08). Technical performance, GPU, and model compatibility assumptions remain UNVERIFIED pending Phase 1B benchmarks.

| ADR | Subject | Status | Approved choice | Approved date | Authority | Next gate |
|---|---|---|---|---|---|---|
| [0001](adr/ADR-0001-api-first-modular-monolith.md) | Headless core & module boundaries | accepted | API-first modular monolith | 2026-10-08 | Product Owner | PH1 |
| [0002](adr/ADR-0002-web-first-ui.md) | Web-first UI and optional native wrapper | accepted | React/Vite now; Tauri later if justified | 2026-10-08 | Product Owner | PH1 |
| [0003](adr/ADR-0003-sqlite-queue.md) | SQLite and reliable queue | accepted | WAL + fenced leases (Phase 2) | 2026-10-08 | Product Owner | PH1 / PH2 |
| [0004](adr/ADR-0004-worker-isolation.md) | Engine workers | accepted | Per-engine runtime + loopback worker process | 2026-10-08 | Product Owner | PH1 |
| [0005](adr/ADR-0005-first-run-security.md) | Bootstrap & authorization | accepted | One-time local setup secret + atomic bootstrap | 2026-10-08 | Product Owner | PH1 |
| [0006](adr/ADR-0006-data-boundaries.md) | Data storage and backup | accepted | Configurable persistent data root; restore evidence | 2026-10-08 | Product Owner | PH1 |
| [0007](adr/ADR-0007-plugin-capabilities.md) | Plugin SDK and trust | accepted | Capability manifest, vetted package, contract tests | 2026-10-08 | Product Owner | PH1 |
| [0008](adr/ADR-0008-mcp-readiness.md) | Future MCP | accepted | Extension point only, independently authorized later | 2026-10-08 | Product Owner | PH6 |

**Approval notes:**
- Gate DOC is formally passed with Product Owner acceptance of the R1.1 baseline.
- Technical performance, model quality, and Windows compatibility remain conditional/unverified until empirical measurement in Phase 1B.
- Phase 1 implementation requires explicit authorization at Gate PH1.
