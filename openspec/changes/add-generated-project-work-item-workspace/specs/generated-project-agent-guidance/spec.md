## MODIFIED Requirements

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the repository MUST provide a read-only onboarding entrypoint such as `make codex-onboard`
- **AND** that entrypoint MUST print repo identity, safe-local verification commands, runtime support status pointers, key documentation routers, and next commands without mutating checked-in files
- **AND** the onboarding docs MUST explain how the read-only onboarding path relates to `OpenSpec`, `bd`, long-running execution plans, and project-owned work-item artifacts

## ADDED Requirements

### Requirement: Project-Owned Work-Item Workspace For Generated Repositories

The template SHALL seed a project-owned workspace for long-running task artifacts in generated repositories.

#### Scenario: Agent needs a canonical place for task-local supporting materials

- **WHEN** a generated-repo task needs extracted notes, bulky inputs, task-local evidence, attachment summaries, or other supporting artifacts that should not live in `OpenSpec`, one exec-plan file, or `src/`
- **THEN** the repository MUST provide a project-owned workspace such as `docs/work-items/`
- **AND** that workspace MUST include a short role guide and a copy-ready starter template
- **AND** the canonical workflow docs MUST explain that `docs/exec-plans/` carries living progress while `docs/work-items/<task-id>/` carries supporting artifacts
- **AND** onboarding output MUST route to this distinction before the agent invents ad-hoc folders like `tasks/roadmap`
