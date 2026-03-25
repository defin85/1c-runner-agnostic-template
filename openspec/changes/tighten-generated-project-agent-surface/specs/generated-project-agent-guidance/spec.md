## ADDED Requirements

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
