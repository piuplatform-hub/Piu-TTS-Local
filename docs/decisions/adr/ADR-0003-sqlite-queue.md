---
id: ADR-0003
title: SQLite-backed queue with fenced leases
status: accepted
approved_date: 2026-10-08
decision_authority: Product Owner
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0003: SQLite-backed queue with fenced leases

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Start with SQLite WAL, initial Phase 1 development dispatcher only; Phase 2 adds atomic queued claim, ownership/fencing, event log and recovery.

## Strongest alternative / trade-off
Redis/PostgreSQL would provide more scalable concurrency but cost more Windows operations. SQLite WAL alone is not a queue guarantee.

## Validation before acceptance/production
Two claimant and crash/restart tests; no duplicate active attempt; no stale artifact commit.

## Status and links
- **Status:** Accepted (2026-10-08 by Product Owner). Directional architectural baseline approved; technical assumptions regarding GPU, model quality, performance, and compatibility remain UNVERIFIED until benchmarked.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
