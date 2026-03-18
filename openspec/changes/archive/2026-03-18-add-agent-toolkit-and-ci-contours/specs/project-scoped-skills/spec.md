## ADDED Requirements

### Requirement: Project-Scoped Skills Package

The template SHALL provide project-scoped skills for common 1C agent operations in generated repositories.

#### Scenario: Generated project includes skill package

- **WHEN** a repository is generated from the template
- **THEN** it MUST include a versioned, project-local skills directory for supported agent workflows
- **AND** the skills MUST be updateable through template updates

### Requirement: Skills Wrap Repo-Owned Scripts

Project-scoped skills SHALL act as thin wrappers over repository-owned scripts instead of becoming a second source of runtime logic.

#### Scenario: Runtime behavior changes in one place

- **WHEN** a capability command changes its flags, artifact contract, or adapter behavior
- **THEN** the canonical implementation MUST live in versioned repo scripts
- **AND** the corresponding skill MUST reference that script contract instead of duplicating the operational logic inline

### Requirement: Intent-To-Capability Mapping

The skill layer SHALL document how common user intents map to skills and to underlying repository entrypoints.

#### Scenario: Agent chooses correct skill and script

- **WHEN** a user asks to dump configuration, load changes, run tests, publish HTTP, or inspect runtime health
- **THEN** the generated project MUST provide a documented mapping from intent to skill
- **AND** the mapping MUST identify the repository-local script entrypoint used for execution
