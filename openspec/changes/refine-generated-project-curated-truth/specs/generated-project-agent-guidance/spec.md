## MODIFIED Requirements

### Requirement: Root Generated Guidance Acts As A Router

The template SHALL keep generated root guidance concise and link it to the most frequent repo-specific workflows instead of embedding all detail in the root instruction file.

#### Scenario: Agent starts from the root of a generated repo

- **WHEN** a new agent loads the root guidance of a generated repository
- **THEN** it MUST see `docs/agent/generated-project-index.md` identified as the canonical onboarding router
- **AND** root `AGENTS.md`, root `README.md`, and `.codex/README.md` MUST stay role-specific pointer surfaces instead of duplicating the full onboarding sequence inline
- **AND** the canonical onboarding router MUST contain the explicit matrix for when to use OpenSpec, `bd`, and `docs/exec-plans/README.md`
- **AND** any detailed Codex workflow explanation beyond the first routing step MUST be delegated to one canonical generated-project workflow document rather than repeated across all root surfaces

## ADDED Requirements

### Requirement: Canonical Codex Workflow Guide For Generated Repositories

The template SHALL ship one canonical Codex workflow guide for generated repositories.

#### Scenario: Agent needs the detailed Codex workflow after the first router step

- **WHEN** an agent already knows the generated-project onboarding router and needs concrete Codex-native workflow guidance
- **THEN** the repository MUST provide one canonical doc such as `docs/agent/codex-workflows.md`
- **AND** that doc MUST cover session controls, review-only flow, long-running flow, skills or MCP pointers, and the relationship between `OpenSpec`, `bd`, and execution plans
- **AND** root pointer surfaces MAY link to that doc but MUST NOT duplicate its detailed control lists inline

### Requirement: Operator-Local Runtime Decision Runbook

The template SHALL seed a project-owned operator-local runtime runbook for generated repositories.

#### Scenario: Agent asks whether an operator-local contour is runnable here

- **WHEN** a generated repository contains operator-local contours such as `doctor` or `xunit`
- **THEN** the repository MUST include a project-owned scaffold such as `docs/agent/operator-local-runbook.md`
- **AND** that runbook MUST be designed to capture preflight checks, required env vars, expected fail-closed states, and canonical entrypoints for operator-local contours
- **AND** `docs/agent/runtime-quickstart.md`, generated onboarding docs, and read-only onboarding output MUST be able to route to that runbook without forcing the agent to assemble the answer from multiple unrelated docs
