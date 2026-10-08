# API contract management policy

**Status:** Proposed, not implemented.

- URL prefix: `/api/v1`. The canonical TTS job endpoint is `POST /api/v1/jobs/speech` (not `/api/v1/speech/jobs`).
- Long-running job submissions return `202 Accepted` + stable job ID, state URL and location; actual generation always belongs to a worker.
- APIs validate permission in application services and use Pydantic/JSON Schema for capabilities; no arbitrary filesystem input paths from web clients.
- Errors conform to RFC 9457. Generated TS SDK is created from committed/exported OpenAPI produced by the running API application; CI compares for drift.
- SSE progress stream does not replace `GET /jobs/{id}`; resilient cursor replay needs durable `job_events` or must fall back to fetching current status.
- `idempotency_key` scoped to authenticated actor plus canonical body digest; mismatched reuse returns HTTP `409 Conflict`.
- Versioning: additive fields/capabilities permitted within v1; breaking contract requires a new version or explicit compatibility period.
- Worker protocol is **internal and separately versioned**; never expose worker loopback HTTP endpoints over LAN.

See [Canonical Contracts](../architecture/CANONICAL_CONTRACTS.md), [API & Data Design](../architecture/API_DATA_DESIGN.md), and [Plugin Architecture](../architecture/PLUGIN_ARCHITECTURE.md).
