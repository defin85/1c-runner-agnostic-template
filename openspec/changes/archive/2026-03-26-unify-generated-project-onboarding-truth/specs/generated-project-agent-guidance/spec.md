## MODIFIED Requirements

### Requirement: Root Generated Guidance Acts As A Router

The template SHALL keep generated root guidance concise and link it to the most frequent repo-specific workflows instead of embedding all detail in the root instruction file.

#### Scenario: Agent starts from the root of a generated repo

- **WHEN** a new agent loads the root guidance of a generated repository
- **THEN** it MUST see `docs/agent/generated-project-index.md` identified as the canonical onboarding router
- **AND** root `AGENTS.md`, root `README.md`, and `.codex/README.md` MUST stay role-specific pointer surfaces instead of duplicating the full onboarding sequence inline
- **AND** the canonical onboarding router MUST contain the explicit matrix for when to use OpenSpec, `bd`, and `docs/exec-plans/README.md`

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the repository MUST provide a read-only onboarding entrypoint such as `make codex-onboard`
- **AND** that entrypoint MUST print repo identity, safe-local verification commands, runtime support status pointers, key documentation routers, and next commands without mutating checked-in files
- **AND** the onboarding docs MUST explain how the read-only onboarding path relates to OpenSpec, `bd`, and long-running execution plans
