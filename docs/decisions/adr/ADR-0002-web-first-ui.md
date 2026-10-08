---
id: ADR-0002
title: Web-first shared frontend
status: accepted
approved_date: 2026-10-08
decision_authority: Product Owner
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0002: Web-first shared frontend

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Use React, TypeScript and Vite with a generated OpenAPI client. Edge app window is a dev convenience, not native packaging. Revisit Tauri/installer separately.

## Strongest alternative / trade-off
Native Qt UI would ease some desktop integration but duplicate browser UI for LAN; Tauri now adds Rust prerequisites.

## Validation before acceptance/production
Localhost UI and browser LAN deploy contract share the same frontend code; no frontend direct engine imports.

## Status and links
- **Status:** Accepted (2026-10-08 by Product Owner). Directional architectural baseline approved; technical assumptions regarding GPU, model quality, performance, and compatibility remain UNVERIFIED until benchmarked.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
