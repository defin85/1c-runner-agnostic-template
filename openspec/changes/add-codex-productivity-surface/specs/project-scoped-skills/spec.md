## MODIFIED Requirements

### Requirement: Project-Scoped Skills Package

The template SHALL provide project-scoped skills for common agent operations in the template source repository and in generated repositories.

#### Scenario: Repository includes a Codex-discoverable skills package

- **WHEN** the template source repo is maintained or a repository is generated from the template
- **THEN** it MUST include a versioned `.agents/skills/` package for supported repeatable workflows
- **AND** any vendor-specific skill facade such as `.claude/skills/` MUST remain a thin packaging layer over the same repo-owned workflow contract
- **AND** the skills MUST remain updateable through template updates

### Requirement: Intent-To-Capability Mapping

The skill layer SHALL document how common user intents map to skills and to underlying repository entrypoints.

#### Scenario: Agent chooses correct skill and script

- **WHEN** a user asks to dump configuration, load changes, run tests, publish HTTP, inspect runtime health, or run the baseline agent verification flow
- **THEN** the repository MUST provide a documented mapping from intent to skill packaging and to the repository-local script or target used for execution
- **AND** the mapping MUST identify the Codex-discoverable skill path and any additional agent-specific wrapper path, if present

## ADDED Requirements

### Requirement: Repo-Local Codex Customization

The repository SHALL provide repo-local Codex customization artifacts that help Codex discover repeatable workflows and optional external context without assuming machine-specific tooling.

#### Scenario: Codex opens the repository

- **WHEN** Codex inspects the repo-local customization surface
- **THEN** `.codex/` guidance and `.agents/skills/` MUST describe repeatable workflows and optional external context
- **AND** the default checked-in Codex configuration MUST remain safe on machines that do not have local MCP binaries or host-specific paths
- **AND** Codex customization MUST point back to repo-owned scripts or agent docs instead of duplicating runtime logic inline
