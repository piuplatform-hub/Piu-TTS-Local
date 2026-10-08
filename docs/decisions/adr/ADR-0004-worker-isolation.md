---
id: ADR-0004
title: Per-engine process isolation
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0004: Per-engine process isolation

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Run engine adapters in independent Python envs, launched by supervisor and authenticated on loopback with ephemeral port. Worker process failure must be handled.

## Strongest alternative / trade-off
HTTP overhead and extra server code vs stdio; process isolation alone is not untrusted code sandboxing.

## Validation before acceptance/production
Kill/crash test isolates API; confirmed worker startup/shutdown; no orphan process where OS supports process job grouping.

## Status and links
- **Status:** Proposed; Product Owner approval required.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
