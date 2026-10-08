# MODEL CONTEXT PROTOCOL (MCP) ARCHITECTURAL READINESS (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-MCP-001-R1  
**Status:** R1.1 — PROPOSED / PENDING OWNER APPROVAL (documentation revision only)  
**Date:** October 2026  

> **Canonical contract:** [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). This R1.1 text is a design proposal, not evidence of implementation or measured performance. For contradictions, canonical contracts and accepted ADRs take precedence.

---

## 1. Architectural Positioning & Official MCP Specification Alignment

The **Model Context Protocol (MCP)**, specified by Anthropic and standardized for AI agent interoperability, provides two standard transport mechanisms:
1. **Stdio Transport:** Communicates via standard input and standard output using JSON-RPC 2.0 messages (ideal for local agent environments like Claude Desktop, Cursor, and CLI agents).
2. **Streamable HTTP Transport (MCP 2026-07-28):** Uses request-scoped HTTP POST to a single endpoint, with either JSON or SSE responses. The legacy GET streaming endpoint and protocol-level sessions are removed in this revision; pinned client compatibility must be reviewed when implementing.

Because AI Voice Studio enforces a strict **Headless Core with an Application Service Layer**, exposing these capabilities to MCP agents should minimize core refactoring **if service contracts and authorization contexts remain transport-independent**:

```
                                ┌─────────────────────────────────────────┐
                                │   External AI Agent (Claude / Cursor)   │
                                └─────────────────────────────────────────┘
                                                     │
                                                     │ MCP JSON-RPC (Stdio or Streamable HTTP)
                                                     ▼
                                ┌─────────────────────────────────────────┐
                                │       MCP Protocol Adapter Layer        │
                                │       (apps/server/adapters/mcp.py)     │
                                └─────────────────────────────────────────┘
                                                     │
                                                     │ Direct Python Service Invocations
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────+
|                           HEADLESS APPLICATION SERVICE LAYER                            |
|   ┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────┐   |
|   │       SpeechService       │  │       ProjectService      │  │VoiceLibraryService│   |
|   └───────────────────────────┘  └───────────────────────────┘  └───────────────────┘   |
|   ┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────┐   |
|   │     JobSchedulerService   │  │   ResourceMonitorService  │  │EngineRegistrySvc  │   |
|   └───────────────────────────┘  └───────────────────────────┘  └───────────────────┘   |
+─────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Standardized MCP Tool Catalog (Future Specification)

When the MCP Server adapter is enabled, it will register the following typed tools:

### `tts_list_engines`
* **Description:** Lists available local speech generation engines and their supported languages.
* **Input Schema:** None.
* **Output:** JSON array of engines, capabilities, and device targets.

### `tts_list_voices`
* **Description:** Retrieves all available preset and user-cloned voices with sample previews.
* **Input Schema:**
  ```json
  { "type": "object", "properties": { "language": { "type": "string" } } }
  ```

### `tts_synthesize`
* **Description:** Submits a text-to-speech generation job using a specified voice.
* **Input Schema:**
  ```json
  {
    "type": "object",
    "required": ["text", "voice_id"],
    "properties": {
      "text": { "type": "string" },
      "voice_id": { "type": "string" },
      "engine_params": { "type": "object", "additionalProperties": true }
    }
  }
  ```

### `tts_get_job_status`
* **Description:** Polls the status of an asynchronous audio generation task.
* **Input Schema:**
  ```json
  {
    "type": "object",
    "required": ["job_id"],
    "properties": { "job_id": { "type": "string" } }
  }
  ```

---

## 3. Strict Boundary: Deferred Implementation Policy

> [!IMPORTANT]
> **MCP implementation remains strictly deferred until Phase 6.**
> * **Rules for Phases 1–4:**
>   1. Do **not** install MCP SDK dependencies or create MCP server files.
>   2. Maintain **Service Layer Hygiene**: Domain services (`SpeechService`, `ProjectService`) must accept and return standard Python Pydantic models. They must **never** import FastAPI `Request`, `Response`, or HTTP headers directly.
>   3. By maintaining this strict boundary, when MCP work is explicitly approved, the adapter can reuse application services. Scope, authentication, user-scoped authorization and asynchronous job semantics may require nontrivial integration work; no line-count guarantee is made.


## 4. Protocol pin and version migration

Design target for future implementation: [MCP 2026-07-28 transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports). The protocol evolution is independent of the application REST/SSE job-progress API. A future MCP adapter must inject an authenticated actor/context into the **same** application authorization policy and must never bypass voice-consent checks. This is a design reference, **not** an implemented MCP server.
