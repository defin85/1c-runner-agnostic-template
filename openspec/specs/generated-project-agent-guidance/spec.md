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
- **THEN** it MUST see explicit links to the generated onboarding route, baseline verify, review guidance, repeatable skills, and long-running execution plans
- **AND** the guidance MUST distinguish between local-only and remote-backed closeout expectations rather than requiring unconditional `git push`

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the onboarding docs MUST describe a linear path from repo identity to safe verification, review flow, and long-running planning
- **AND** that path MUST link to repo-owned entrypoints such as `make agent-verify`, `env/README.md`, `.agents/skills/README.md`, `.codex/README.md`, and `docs/exec-plans/README.md`

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

The template SHALL seed truthful project-specific context artifacts for generated repositories without relying on template-source placeholders.

#### Scenario: New generated project is created

- **WHEN** `copier copy` renders a generated repository
- **THEN** the repository MUST include concrete initial project context files derived from Copier answers and current repository layout
- **AND** those files MUST NOT contain raw template placeholder markers such as `<...>` or instructions addressed to the template source repository
- **AND** the generated repository MUST keep curated project context separate from machine-generated inventory artifacts

### Requirement: Verification Matrix For Generated Repositories

The template SHALL provide a generated-project verification map that distinguishes safe local checks from profile-required and provisioned-runtime contours.

#### Scenario: Agent asks which checks are safe to run first

- **WHEN** an agent needs a first-pass verification path in a generated repository
- **THEN** the repository documentation MUST classify relevant commands by prerequisites, side effects, and expected artifacts
- **AND** it MUST provide a documented no-1C baseline path
- **AND** runtime-profile-required and provisioned/self-hosted 1C contours MUST be marked explicitly as deeper verification layers

### Requirement: Side-Effect-Transparent Context Export

The template SHALL provide side-effect-transparent utilities for inspecting and refreshing agent context in generated repositories.

#### Scenario: Agent inspects context export contract

- **WHEN** an agent invokes repo-owned context export tooling without explicit write intent
- **THEN** the tooling MUST provide help, preview, or check behavior without mutating checked-in files
- **AND** explicit write behavior MUST require a dedicated flag or command path
- **AND** refreshed machine-generated artifacts MUST use deterministic filenames or suffixes that signal generated status
