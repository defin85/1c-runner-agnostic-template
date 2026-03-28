# project-scoped-skills Specification

## Purpose
TBD - created by archiving change add-agent-toolkit-and-ci-contours. Update Purpose after archive.
## Requirements
### Requirement: Project-Scoped Skills Package

The template SHALL provide project-scoped skills for common agent operations in the template source repository and in generated repositories.

#### Scenario: Repository includes a Codex-discoverable skills package

- **WHEN** the template source repo is maintained or a repository is generated from the template
- **THEN** it MUST include a versioned `.agents/skills/` package for supported repeatable workflows
- **AND** any vendor-specific skill facade such as `.claude/skills/` MUST remain a thin packaging layer over the same repo-owned workflow contract
- **AND** the skills MUST remain updateable through template updates

### Requirement: Skills Wrap Repo-Owned Scripts

Project-scoped skills SHALL act as thin wrappers over repository-owned scripts instead of becoming a second source of runtime logic.

#### Scenario: Runtime behavior changes in one place

- **WHEN** a capability command changes its flags, artifact contract, or adapter behavior
- **THEN** the canonical implementation MUST live in versioned repo scripts
- **AND** the corresponding skill MUST reference that script contract instead of duplicating the operational logic inline

### Requirement: Intent-To-Capability Mapping

The skill layer SHALL document how common user intents map to skills and to underlying repository entrypoints.

#### Scenario: Agent chooses correct skill and script

- **WHEN** a user asks to dump configuration, load changes, run tests, publish HTTP, inspect runtime health, or run the baseline agent verification flow
- **THEN** the repository MUST provide a documented mapping from intent to skill packaging and to the repository-local script or target used for execution
- **AND** the mapping MUST identify the Codex-discoverable skill path and any additional agent-specific wrapper path, if present

### Requirement: Repo-Local Codex Customization

The repository SHALL provide repo-local Codex customization artifacts that help Codex discover repeatable workflows and optional external context without assuming machine-specific tooling.

#### Scenario: Codex opens the repository

- **WHEN** Codex inspects the repo-local customization surface
- **THEN** `.codex/` guidance and `.agents/skills/` MUST describe repeatable workflows and optional external context
- **AND** the default checked-in Codex configuration MUST remain safe on machines that do not have local MCP binaries or host-specific paths
- **AND** Codex customization MUST point back to repo-owned scripts or agent docs instead of duplicating runtime logic inline

### Requirement: Intent Mapping For Diff-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ только текущие source changes".

#### Scenario: Agent looks for a repeatable diff-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ только текущий diff исходников
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates

### Requirement: Intent Mapping For Task-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ уже закомиченные изменения задачи".

#### Scenario: Agent looks for a repeatable task-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ изменения конкретной задачи, уже попавшие в commit history
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН документировать canonical selectors `--bead`, `--work-item` и `--range`
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates

