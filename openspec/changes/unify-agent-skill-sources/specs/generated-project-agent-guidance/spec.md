## ADDED Requirements

### Requirement: Publication On Request

The generated `AGENTS.md` template block SHALL NOT make push a mandatory closeout step and SHALL defer search routing to a project-owned search runbook when one exists.

#### Scenario: Agent finishes code changes in a remote-backed repository

- **WHEN** the verified changes are ready in a repository with a writable remote
- **THEN** the guidance MUST allow push only when the user or the selected publication process asks for it
- **AND** it MUST still distinguish local-only and remote-backed repositories

#### Scenario: Project defines its own search runbook

- **WHEN** the project documents a search runbook
- **THEN** the template Search Playbook MUST state that the project runbook takes precedence
