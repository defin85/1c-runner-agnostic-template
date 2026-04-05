# generated-project-agent-guidance Specification

## Purpose
TBD - created by archiving change tighten-generated-project-agent-surface. Update Purpose after archive.
## Requirements
### Requirement: Generated Project Instruction Routing

The template SHALL ship generated-project-safe routing in shared docs and directory-local instruction files so that generated repos do not start from a source-repo-centric onboarding path.

#### Scenario: Generated repo enters nested docs and automation directories

- **WHEN** an agent opens `docs/`, `automation/`, or `src/` inside a generated repository created from the template
- **THEN** the active routing guidance MUST point to generated-project onboarding and project-owned truth instead of telling the agent to start with source-repo-centric `docs/agent/index.md`
- **AND** shared directory-local instructions MUST describe their role in a way that remains valid both for the template source repo and for generated repos

### Requirement: Root Generated Guidance Acts As A Router

The template SHALL keep generated root guidance concise and link it to the most frequent repo-specific workflows instead of embedding all detail in the root instruction file.

#### Scenario: Agent starts from the root of a generated repo

- **WHEN** a new agent loads the root guidance of a generated repository
- **THEN** it MUST see `docs/agent/generated-project-index.md` identified as the canonical onboarding router
- **AND** root `AGENTS.md`, root `README.md`, and `.codex/README.md` MUST stay role-specific pointer surfaces instead of duplicating the full onboarding sequence inline
- **AND** the canonical onboarding router MUST contain the explicit matrix for when to use OpenSpec, `bd`, and `docs/exec-plans/README.md`
- **AND** any detailed Codex workflow explanation beyond the first routing step MUST be delegated to one canonical generated-project workflow document rather than repeated across all root surfaces

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex, including an explicit AI-readiness view for template-managed workflows.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the repository MUST provide a read-only onboarding entrypoint such as `make codex-onboard`
- **AND** that entrypoint MUST print repo identity, safe-local verification commands, runtime support status pointers, AI-readiness status for template-managed skills, key documentation routers, and next commands without mutating checked-in files
- **AND** that entrypoint MUST route to one canonical compact surface for project-aware recommended skills or workflows when such hints are available
- **AND** the onboarding docs MUST explain how the read-only onboarding path relates to `OpenSpec`, `bd`, long-running execution plans, and project-owned work-item artifacts

### Requirement: Generated-Project Root Entry Point

The template SHALL render a generated-project-first onboarding surface for agents in generated repositories.

#### Scenario: New agent lands in a generated repository root

- **WHEN** an agent reads the generated repository root `README.md` or `AGENTS.md`
- **THEN** those entry points MUST identify the repository as a generated project rather than as the template source repository
- **AND** they MUST point to the project map, the verification matrix, and the template-maintenance guide
- **AND** template-maintenance workflow MUST NOT appear as the primary onboarding or feature-delivery path for generated-project work

### Requirement: Update-Safe Agent Artifact Ownership

The template SHALL define update-safe ownership classes for agent-facing artifacts in generated repositories.

#### Scenario: Generated project refreshes template-managed assets

- **WHEN** a generated repository runs `copier update` or an equivalent repo-owned template refresh path
- **THEN** template-managed agent-facing assets MAY be refreshed automatically through template updates
- **AND** project-owned identity and domain-context artifacts MUST remain preserved or be isolated outside template-managed blocks
- **AND** generated-derived artifacts MUST be refreshable through explicit repo-owned commands rather than silent manual merge expectations
- **AND** local-private machine-specific settings MUST remain outside the checked-in template contract

### Requirement: Concrete Project-Owned Context Seeds

The template SHALL seed truthful project-specific context artifacts for generated repositories without relying on template-source placeholders, and those seeds MUST contain repo-derived first-pass facts when the repository shape already exposes them.

#### Scenario: New generated project is created with discoverable repo shape

- **WHEN** `copier copy` renders a generated repository and current repository layout or metadata already expose high-signal facts such as configuration identity, source roots, or representative hot zones
- **THEN** the repository MUST include concrete initial project context files derived from Copier answers, current repository layout, and those repo-derived facts
- **AND** those files MUST include first-pass routing hints for likely change scenarios when that information is already available
- **AND** those files MUST NOT contain raw template placeholder markers such as `<...>` or instructions addressed to the template source repository
- **AND** the generated repository MUST keep curated project context separate from machine-generated inventory artifacts

### Requirement: Verification Matrix For Generated Repositories

Шаблон MUST предоставлять generated-project verification map, которая различает safe local checks, profile-required contours, unsupported contours и provisioned-runtime contours.

#### Scenario: Agent asks which checks are safe to run first

- **WHEN** агенту нужен first-pass verification path в generated repository
- **THEN** repository documentation ДОЛЖНА классифицировать релевантные команды по prerequisites, side effects, expected artifacts и support status
- **AND** она ДОЛЖНА давать задокументированный no-1C baseline path
- **AND** runtime-profile-required и provisioned/self-hosted 1C contours ДОЛЖНЫ быть явно помечены как более глубокие verification layers
- **AND** любой unsupported или placeholder contour НЕ ДОЛЖЕН показываться как зелёный baseline-ready verification step

### Requirement: Side-Effect-Transparent Context Export

The template SHALL provide side-effect-transparent utilities for inspecting and refreshing agent context in generated repositories.

#### Scenario: Agent inspects context export contract

- **WHEN** an agent invokes repo-owned context export tooling without explicit write intent
- **THEN** the tooling MUST provide help, preview, or check behavior without mutating checked-in files
- **AND** explicit write behavior MUST require a dedicated flag or command path
- **AND** refreshed machine-generated artifacts MUST use deterministic filenames or suffixes that signal generated status

### Requirement: Local Working-Area Routing For Generated Repositories

Шаблон MUST поставлять краткий directory-local routing guidance для generated-project work в самых friction-heavy рабочих зонах.

#### Scenario: Agent enters env, tests, scripts, or dense source roots in a generated repository

- **WHEN** агент открывает `env/`, `tests/`, `scripts/` или `src/cf/` внутри generated repository
- **THEN** локальный `AGENTS.md` ДОЛЖЕН маршрутизировать агента к релевантным truth sources и guardrails для этой области
- **AND** локальный guidance ДОЛЖЕН оставаться уже root router, а не дублировать весь repository manual

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

### Requirement: Project-Owned Work-Item Workspace For Generated Repositories

The template SHALL seed a project-owned workspace for long-running task artifacts in generated repositories.

#### Scenario: Agent needs a canonical place for task-local supporting materials

- **WHEN** a generated-repo task needs extracted notes, bulky inputs, task-local evidence, attachment summaries, or other supporting artifacts that should not live in `OpenSpec`, one exec-plan file, or `src/`
- **THEN** the repository MUST provide a project-owned workspace such as `docs/work-items/`
- **AND** that workspace MUST include a short role guide and a copy-ready starter template
- **AND** the canonical workflow docs MUST explain that `docs/exec-plans/` carries living progress while `docs/work-items/<task-id>/` carries supporting artifacts
- **AND** onboarding output MUST route to this distinction before the agent invents ad-hoc folders like `tasks/roadmap`

### Requirement: Generated Repo AI-Readiness Routing

The template SHALL route generated repositories through one canonical AI-readiness surface before the agent explores the full skill catalog.

#### Scenario: New agent needs the shortest safe path to useful workflows

- **WHEN** a new agent enters a generated repository through root routing docs or the read-only onboarding command
- **THEN** the generated-project guidance MUST identify one canonical readiness or recommendation surface for template-managed skills
- **AND** that surface MUST distinguish compact first-hour recommendations from the full `.agents/skills/` catalog
- **AND** if executable imported skills need extra local bootstrap, the same routing layer MUST point to the canonical readiness/bootstrap path instead of leaving the agent to infer it from helper crashes

