# AI Voice Studio — Documentation Hub

> **Current status:** R1.1 documentation **accepted** as official baseline by Product Owner (2026-10-08). **Gate DOC passed; Phase 1 implementation has not started.** Technical hardware/model performance assumptions remain unverified pending Phase 1B benchmarks.

## Quick navigation

| Need to find… | Go to |
|---|---|
| Current architectural contract | [Canonical Contracts](architecture/CANONICAL_CONTRACTS.md) |
| System architecture diagrams | [Target Architecture](architecture/TARGET_ARCHITECTURE.md) |
| Architectural justification | [Architecture Review](architecture/ARCHITECTURE_REVIEW.md) · [Technology Decisions](architecture/TECHNOLOGY_DECISIONS.md) |
| Plugin/engine integration | [Engine Plugin Architecture](architecture/PLUGIN_ARCHITECTURE.md) |
| Endpoints, DB and job design | [API & Data Design](architecture/API_DATA_DESIGN.md) · [API Policy](specs/API_CONTRACT_POLICY.md) |
| Security/deployment | [Security & Deployment](architecture/SECURITY_DEPLOYMENT.md) |
| Future MCP | [MCP Readiness](architecture/MCP_READINESS.md) |
| Delivery phases | [Implementation Roadmap](architecture/IMPLEMENTATION_ROADMAP.md) · [Phase 1 Plan](plans/PHASE_01_FOUNDATION.md) |
| Accepted/proposed decisions | [Decision Register](decisions/DECISION_LOG.md) · [ADRs](decisions/README.md) |
| Remaining questions & gates | [Open Decisions](architecture/OPEN_DECISIONS.md) |
| Tests / implementation reports | [Reports](reports/README.md) |
| Candidate improvements & proposals | [Ideas](ideas/README.md) |
| Verified research & evidence | [Source Register](research/SOURCE_REGISTER.md) · [Engine Spike](research/ENGINE_FEASIBILITY_MATRIX.md) |
| Running/operating locally | [Operations](operations/README.md) |
| Document creation conventions | [Governance](GOVERNANCE.md) · [Templates](templates/) |
| What changed since R1 | [R1.1 Changelog](architecture/R1_1_CHANGELOG.md) · [Docs Changelog](CHANGELOG.md) |
| Prior untouched originals | [archive/r1-original](archive/r1-original/) |

## Organizational structure

```text
docs/
├── README.md                  # This navigation hub
├── GOVERNANCE.md              # Naming, ownership, status, review, archiving
├── CHANGELOG.md               # Documentation change log
├── architecture/              # Canonical blueprint and 9 synchronized R1.1 specs
├── decisions/                 # ADRs and owner approvals (append-only history)
│   └── adr/
├── plans/                     # Approved/proposed phase plans and checkpoints
├── reports/                   # Dated evidence, reviews and benchmarks
│   ├── reviews/
│   └── benchmarks/
├── ideas/                     # Idea intake, backlog, evaluation
├── research/                  # Sources, feasibility unknowns and model evidence
├── specs/                     # API and other testable public contracts
├── operations/                # Handoffs, setup, deployment and runbooks
├── templates/                 # ADR, plan, report, idea, evidence templates
└── archive/                   # Immutable historical drafts / superseded docs
    └── r1-original/
```

## Five operating rules

1. **One source of truth per topic.** API paths and semantics live in [Canonical Contracts](architecture/CANONICAL_CONTRACTS.md); implementation must generate OpenAPI and typed SDK from a running service. Other documents should link instead of restating conflicting versions.
2. **No claim without evidence.** `proposed`/`unverified`/`tested` are distinct labels. Successful doc creation ≠ successful inference test.
3. **Changes to critical architecture require ADRs.** Don't overwrite an old accepted decision; mark it superseded and link the replacement.
4. **Every phase generates a plan AND an evidence report.** Link git revision, test output, issues, rollback, owner acceptance.
5. **No implicit authorization.** Docs revision does not permit downloading weights, installing software, opening LAN ports, or executing code on the PC.

## Updating after each phase

- Start with a dated plan in `plans/` (use [PLAN template](templates/PLAN_TEMPLATE.md)).
- Log architectural changes in an ADR before implementing them.
- Attach a dated report in `reports/` referencing commands, tests and commits (use [REPORT template](templates/REPORT_TEMPLATE.md)).
- Update [`decisions/DECISION_LOG.md`](decisions/DECISION_LOG.md), [`CHANGELOG.md`](CHANGELOG.md), the roadmap and this README if applicable.
- Preserve superseded revisions in `archive/`. Never silently rewrite history.
