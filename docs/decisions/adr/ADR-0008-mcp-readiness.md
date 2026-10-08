---
id: ADR-0008
title: Future MCP as transport adapter
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0008: Future MCP as transport adapter

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
No MCP implementation until approved; maintain application service boundaries and user-scoped policy; when implementing pin the protocol version (current reference 2026-07-28).

## Strongest alternative / trade-off
Implementing MCP now raises auth and interoperability complexity before speech engine stability.

## Validation before acceptance/production
Future adapter exposes tools without bypassing permissions, does not change core inference logic.

## Status and links
- **Status:** Proposed; Product Owner approval required.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
