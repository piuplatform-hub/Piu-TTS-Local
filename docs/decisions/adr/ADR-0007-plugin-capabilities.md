---
id: ADR-0007
title: Versioned engine adapter and trust policy
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0007: Versioned engine adapter and trust policy

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Define versioned capability schemas and optional features; verify package provenance and explicit approval; keep model vs engine vs voice separate.

## Strongest alternative / trade-off
Hardcoded per-model code is faster short term but brittle; adapter SDK has ongoing versioning costs.

## Validation before acceptance/production
Mock + VieNeu + Qwen share contract; adding 3rd compatible adapter changes no core business logic.

## Status and links
- **Status:** Proposed; Product Owner approval required.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
