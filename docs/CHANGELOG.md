# Documentation changelog

## 2026-10-08 — R1.1 Documentation Baseline Accepted (Gate DOC Passed)

- Product Owner formally accepted the Architecture R1.1 documentation pack as the official architectural baseline.
- Updated all 8 ADRs (ADR-0001 through ADR-0008) status to `accepted` under Product Owner authority.
- Recorded explicit condition: Hardware, GPU memory, inference latency, model audio quality, and Windows compatibility assumptions remain UNVERIFIED pending Phase 1B benchmarks.
- Published review report: `docs/reports/reviews/2026-10-08-documentation-acceptance.md`.
- Phase 1 implementation remains pending separate authorization (Gate PH1).

## 2026-10-08 — R1.1 (Proposed)

- Imported 9 Gemini R1 documents and kept exact originals in `archive/r1-original/`.
- Created long-term docs hierarchy, governance, versioned ADR register, phase plan, reports, ideas/research/specs/operations and templates.
- Reconciled canonical TTS API path (`/api/v1/jobs/speech`), safer SQLite claim/recovery semantics and stale worker fencing design.
- Hardened first-run bootstrap design; clarified plugin integrity is not signature/authenticity.
- Updated MCP design reference to 2026-07-28; qualified FFmpeg distribution obligations.
- Unified Phase 1 minimal mocked end-to-end acceptance and separated Phase 1B permissions.
- Marked model GPU figures as unverified pending benchmarks.

**Note:** This changelog records documentation edits only, not code or tests executed on the PC.
