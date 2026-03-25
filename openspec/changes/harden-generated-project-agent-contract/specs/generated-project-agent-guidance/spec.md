## MODIFIED Requirements

### Requirement: Verification Matrix For Generated Repositories

Шаблон MUST предоставлять generated-project verification map, которая различает safe local checks, profile-required contours, unsupported contours и provisioned-runtime contours.

#### Scenario: Agent asks which checks are safe to run first

- **WHEN** агенту нужен first-pass verification path в generated repository
- **THEN** repository documentation ДОЛЖНА классифицировать релевантные команды по prerequisites, side effects, expected artifacts и support status
- **AND** она ДОЛЖНА давать задокументированный no-1C baseline path
- **AND** runtime-profile-required и provisioned/self-hosted 1C contours ДОЛЖНЫ быть явно помечены как более глубокие verification layers
- **AND** любой unsupported или placeholder contour НЕ ДОЛЖЕН показываться как зелёный baseline-ready verification step

### Requirement: Codex-First Generated Runbook

Шаблон MUST поставлять generated-project-first runbook для первых минут работы в Codex и для наиболее типичных generated-project workflows.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** Codex agent стартует в generated repository и ещё не собрал project context
- **THEN** onboarding docs ДОЛЖНЫ описывать линейный путь от repo identity к safe verification, review flow и long-running planning
- **AND** этот путь ДОЛЖЕН ссылаться на repo-owned entrypoints вроде `make agent-verify`, `env/README.md`, `.agents/skills/README.md`, `.codex/README.md` и `docs/exec-plans/README.md`

#### Scenario: Codex agent chooses a work mode

- **WHEN** Codex agentу нужно выбрать между `first 15 minutes`, `long-running change`, `runtime investigation`, `review-only session` и `parallel research`
- **THEN** shared runbook ДОЛЖЕН объяснять, какой repo-local playbook применять
- **AND** он ДОЛЖЕН сопоставлять релевантные controls, такие как `/plan`, `/review`, `/ps`, `/compact`, `/agent`, worktrees и bounded subagents, с этим workflow
- **AND** plain command list без workflow guidance НЕ ДОЛЖЕН оставаться единственным Codex-facing contract

## ADDED Requirements

### Requirement: Local Working-Area Routing For Generated Repositories

Шаблон MUST поставлять краткий directory-local routing guidance для generated-project work в самых friction-heavy рабочих зонах.

#### Scenario: Agent enters env, tests, or scripts in a generated repository

- **WHEN** агент открывает `env/`, `tests/` или `scripts/` внутри generated repository
- **THEN** локальный `AGENTS.md` ДОЛЖЕН маршрутизировать агента к релевантным truth sources и guardrails для этой области
- **AND** локальный guidance ДОЛЖЕН оставаться уже root router, а не дублировать весь repository manual
