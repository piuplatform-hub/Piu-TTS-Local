# MODEL CONTEXT PROTOCOL (MCP) ARCHITECTURAL READINESS (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-MCP-001-R1  
**Status:** REVISED ARCHITECTURE (R1) — AWAITING PHASE 1 AUTHORIZATION  
**Date:** October 2026  

---

## 1. Architectural Positioning & Official MCP Specification Alignment

The **Model Context Protocol (MCP)**, specified by Anthropic and standardized for AI agent interoperability, provides two standard transport mechanisms:
1. **Stdio Transport:** Communicates via standard input and standard output using JSON-RPC 2.0 messages (ideal for local agent environments like Claude Desktop, Cursor, and CLI agents).
2. **Streamable HTTP Transport (SSE + POST):** Uses an HTTP Server-Sent Events (SSE) stream for server-to-client messages and standard HTTP POST requests for client-to-server tool invocations (ideal for networked agents and LAN servers).

Because AI Voice Studio enforces a strict **Headless Core with an Application Service Layer**, exposing these capabilities to MCP agents requires **zero refactoring of business logic**:

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
      "speed": { "type": "number", "default": 1.0 }
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
>   3. By maintaining this strict boundary, when Phase 6 arrives, implementing the complete MCP Server adapter will be an isolated ~200-line translation layer without touching existing business code.
