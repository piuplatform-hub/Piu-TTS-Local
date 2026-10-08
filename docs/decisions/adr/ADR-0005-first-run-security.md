---
id: ADR-0005
title: Secure onboarding and authorization
status: accepted
approved_date: 2026-10-08
decision_authority: Product Owner
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0005: Secure onboarding and authorization

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Use local one-time bootstrap secret and atomic first-admin gate; authenticated application services enforce ownership. LAN requires independent hardening gate.

## Strongest alternative / trade-off
A local single-user bypass is simpler but unsafe on shared hosts/browser and future LAN access.

## Validation before acceptance/production
Concurrent bootstrap attempts create at most one admin; unauthorized artifact and voice access denied.

## Status and links
- **Status:** Accepted (2026-10-08 by Product Owner). Directional architectural baseline approved; technical assumptions regarding GPU, model quality, performance, and compatibility remain UNVERIFIED until benchmarked.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
