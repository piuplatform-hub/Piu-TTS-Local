# R1.1 documentation consistency change log

**Status:** Proposed · **Date:** 2026-10-08 · **No implementation or hardware benchmarks were executed.**

| ID | Corrective edit | Canonical location |
|---|---|---|
| DOC-01 | API path harmonized to `/api/v1/jobs/speech` | API_DATA_DESIGN, TARGET_ARCHITECTURE, CANONICAL_CONTRACTS |
| DOC-02 | Removed invalid SQLite `UPDATE ... LIMIT` dependent example; separated claim vs stale recovery, added fencing and idempotency scope | API_DATA_DESIGN, TECHNOLOGY_DECISIONS |
| DOC-03 | First-run admin setup gated by local one-use secret and transaction; no implicit localhost admin | SECURITY_DEPLOYMENT, API_DATA_DESIGN |
| DOC-04 | SHA-256 placeholder removed; provenance and runtime privileges clarified | PLUGIN_ARCHITECTURE |
| DOC-05 | Phase 1 Mock vertical slice acceptance distinguished from Phase 2 durability; Phase 1B separately authorized | IMPLEMENTATION_ROADMAP, OPEN_DECISIONS |
| DOC-06 | FFmpeg license depends on exact build/configuration, not subprocess call alone | SECURITY_DEPLOYMENT, TECHNOLOGY_DECISIONS |
| DOC-07 | Adopt MCP 2026-07-28 design reference (no legacy GET stream), without implementing MCP | MCP_READINESS |
| DOC-08 | Removed fixed RAM/VRAM certainty, fixed port assumptions and blanket Windows process guarantees | TARGET_ARCHITECTURE, TECHNOLOGY_DECISIONS |
| DOC-09 | Data root configurable; consistent DB + audio backups required | SECURITY_DEPLOYMENT, API_DATA_DESIGN |
| DOC-10 | Added durable knowledge structure, governance, ADRs, plan/report/idea templates, source register | docs/README, docs/GOVERNANCE, decisions, templates |

## Remaining unverified or future decisions
- Authentic device benchmark and support matrix for VieNeu-TTS CPU/clone and Qwen3-TTS CustomVoice GPU.
- Production session transport (cookie strategy), Windows service/tray design, exact FFmpeg binary distribution and per-model licenses.
- Scheduler retry/fencing/cancel implementation; SQL must be validated on deployed SQLite version.
- Manifest signing/trust policy and approved plugin distribution mechanics.
- `docs/` in this package is **not yet installed on the user's PC**. Gemini must inspect and merge it safely with the current workspace.

## Source references
- [SQLite UPDATE](https://www.sqlite.org/lang_update.html) and [RETURNING](https://www.sqlite.org/lang_returning.html)
- [SQLite compile-time option](https://www.sqlite.org/compile.html)
- [FFmpeg legal](https://www.ffmpeg.org/legal.html)
- [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [HTTP Problem Details RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
