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
| [0009](adr/ADR-0009-runner-process-and-online-backup.md) | Standalone runner & online backup | accepted | Decoupled scheduler process + SQLite Online Backup API | 2026-10-08 | Product Owner | PH4 |
| [0010](adr/ADR-0010-single-host-reverse-proxy-and-tls.md) | Reverse proxy & internal TLS | proposed | Caddy Server reverse proxy + automatic internal HTTPS | 2026-10-09 | Product Owner | PH5 |
| [0011](adr/ADR-0011-multi-user-rbac-and-resource-fairness.md) | Multi-user RBAC & fair scheduling | proposed | Per-user round-robin + storage quotas + strict RBAC | 2026-10-09 | Product Owner | PH5 |
| [0012](adr/ADR-0012-windows-service-and-process-lifecycle.md) | Windows services & recovery | proposed | WinSW wrapper + auto-restart + startup crash recovery | 2026-10-09 | Product Owner | PH5 |

**Approval notes:**
- Gate DOC is formally passed with Product Owner acceptance of the R1.1 baseline.
- Phase 0–4 baselines are fully accepted and verified (Git commit `24b3102`).
- Phase 5 is in PLANNING GATE state (ADR-0010 through ADR-0012 are proposed awaiting Product Owner authorization).
