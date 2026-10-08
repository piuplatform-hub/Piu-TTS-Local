---
id: ADR-0006
title: Persistent data outside binaries
status: proposed
owner: Product Owner
created: 2026-10-08
updated: 2026-10-08
---

# ADR-0006: Persistent data outside binaries

## Context
AI Voice Studio must serve local Windows and trusted office LAN users, evolve beyond VieNeu and Qwen3, and operate within an RTX 3050 6GB + 16GB RAM initial host. This is an architectural decision, not tested implementation.

## Decision proposed
Use configurable `STUDIO_DATA_DIR`; treat D:\AIVoiceStudioData as a proposed path; back up DB and associated media; test restores.

## Strongest alternative / trade-off
Single fixed D: path simplifies first machine only but fails other PCs/permission scenarios.

## Validation before acceptance/production
Upgrade preserves models/media; restore sample project and playable WAV from isolated backup.

## Status and links
- **Status:** Proposed; Product Owner approval required.
- **Sources:** [Canonical Contracts](../../architecture/CANONICAL_CONTRACTS.md), [Original R1 decisions](../../architecture/TECHNOLOGY_DECISIONS.md), [Open Decisions](../../architecture/OPEN_DECISIONS.md).
- **Superseded by:** None.
