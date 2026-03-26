## MODIFIED Requirements

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the repository MUST provide a read-only onboarding entrypoint such as `make codex-onboard`
- **AND** that entrypoint MUST print repo identity, safe-local verification commands, runtime support status pointers, key documentation routers, and next commands without mutating checked-in files
- **AND** the onboarding docs MUST explain how the read-only onboarding path relates to OpenSpec, `bd`, and long-running execution plans
- **AND** the read-only onboarding path MUST surface the key Codex session controls needed in the first minutes, including `/plan`, `/compact`, `/review`, `/ps`, and `/mcp`

### Requirement: Local Working-Area Routing For Generated Repositories

Шаблон MUST поставлять краткий directory-local routing guidance для generated-project work в самых friction-heavy рабочих зонах.

#### Scenario: Agent enters env, tests, scripts, or dense source roots in a generated repository

- **WHEN** агент открывает `env/`, `tests/`, `scripts/` или `src/cf/` внутри generated repository
- **THEN** локальный `AGENTS.md` ДОЛЖЕН маршрутизировать агента к релевантным truth sources и guardrails для этой области
- **AND** локальный guidance ДОЛЖЕН оставаться уже root router, а не дублировать весь repository manual

## ADDED Requirements

### Requirement: Project-Owned Code Architecture Map

The template SHALL seed a project-owned code architecture map for generated repositories.

#### Scenario: New generated repo needs a practical code navigation bridge

- **WHEN** a generated repository is created or refreshed from the template
- **THEN** it MUST include a project-owned `docs/agent/architecture-map.md` scaffold
- **AND** that scaffold MUST be designed to capture representative change scenarios, likely paths, relevant metadata objects, and nearby runbooks or tests
- **AND** generated onboarding docs MUST treat that file as curated project-owned truth rather than as a template-managed manual

### Requirement: Project-Specific Runtime Quick Reference

The template SHALL seed a concise runtime quick reference for generated repositories.

#### Scenario: Agent asks what can be run and with which prerequisites

- **WHEN** an agent needs a short answer for runtime status, canonical commands, and required env vars in a generated repository
- **THEN** the repository MUST include a project-owned `docs/agent/runtime-quickstart.md` scaffold
- **AND** that quick reference MUST point back to `automation/context/runtime-support-matrix.md` and `.json` as the checked-in runtime truth
- **AND** it MUST distinguish `supported`, `operator-local`, `unsupported`, and `provisioned` contours without forcing the agent to read the entire general-purpose runtime contract first

### Requirement: Project-Specific Baseline Extension Slot

The template SHALL provide a documented extension slot for project-owned no-1C baseline smoke in generated repositories.

#### Scenario: Generated repo adds project-owned agent/runtime smoke

- **WHEN** a generated repository defines an extra project-owned no-1C smoke contour beyond the shared template baseline
- **THEN** generated onboarding and read-only onboarding output MUST be able to advertise that contour as a project-specific extension
- **AND** the extension MUST remain clearly separate from the template-managed baseline path
- **AND** the absence of a project-specific extension MUST NOT make the generated repository look incomplete by default
