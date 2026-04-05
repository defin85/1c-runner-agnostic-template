## MODIFIED Requirements

### Requirement: Codex-First Generated Runbook

The template SHALL ship a generated-project-first runbook for the first minutes of work in Codex, including an explicit AI-readiness view for template-managed workflows.

#### Scenario: Codex agent needs a first-hour workflow

- **WHEN** a Codex agent starts in a generated repository and has not yet built project context
- **THEN** the repository MUST provide a read-only onboarding entrypoint such as `make codex-onboard`
- **AND** that entrypoint MUST print repo identity, safe-local verification commands, runtime support status pointers, AI-readiness status for template-managed skills, key documentation routers, and next commands without mutating checked-in files
- **AND** that entrypoint MUST route to one canonical compact surface for project-aware recommended skills or workflows when such hints are available
- **AND** the onboarding docs MUST explain how the read-only onboarding path relates to `OpenSpec`, `bd`, long-running execution plans, and project-owned work-item artifacts

### Requirement: Concrete Project-Owned Context Seeds

The template SHALL seed truthful project-specific context artifacts for generated repositories without relying on template-source placeholders, and those seeds MUST contain repo-derived first-pass facts when the repository shape already exposes them.

#### Scenario: New generated project is created with discoverable repo shape

- **WHEN** `copier copy` renders a generated repository and current repository layout or metadata already expose high-signal facts such as configuration identity, source roots, or representative hot zones
- **THEN** the repository MUST include concrete initial project context files derived from Copier answers, current repository layout, and those repo-derived facts
- **AND** those files MUST include first-pass routing hints for likely change scenarios when that information is already available
- **AND** those files MUST NOT contain raw template placeholder markers such as `<...>` or instructions addressed to the template source repository
- **AND** the generated repository MUST keep curated project context separate from machine-generated inventory artifacts

## ADDED Requirements

### Requirement: Generated Repo AI-Readiness Routing

The template SHALL route generated repositories through one canonical AI-readiness surface before the agent explores the full skill catalog.

#### Scenario: New agent needs the shortest safe path to useful workflows

- **WHEN** a new agent enters a generated repository through root routing docs or the read-only onboarding command
- **THEN** the generated-project guidance MUST identify one canonical readiness or recommendation surface for template-managed skills
- **AND** that surface MUST distinguish compact first-hour recommendations from the full `.agents/skills/` catalog
- **AND** if executable imported skills need extra local bootstrap, the same routing layer MUST point to the canonical readiness/bootstrap path instead of leaving the agent to infer it from helper crashes
