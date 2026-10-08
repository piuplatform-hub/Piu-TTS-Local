---
id: ADR-0001
title: API-first headless modular monolith
status: accepted
approved_date: 2026-10-08
decision_authority: Product Owner
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0001: API-first headless modular monolith

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Keep business application services transport/UI-independent. Use modular monolith for control plane and isolated workers for CPU/GPU inference.

## Strongest alternative / trade-off
Microservices add service discovery, distributed failures and deployment complexity for one Windows host.

## Validation before acceptance/production
Core integration tests; no FastAPI Request imports in application services; same use-case accessible to mock REST adapter.

## Status and links
- **Status:** Accepted (2026-10-08 by Product Owner). Directional architectural baseline approved; technical assumptions regarding GPU, model quality, performance, and compatibility remain UNVERIFIED until benchmarked.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
