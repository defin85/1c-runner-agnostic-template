## ADDED Requirements

### Requirement: Repository-Level Agent Entry Point

The template source repository SHALL expose a concise root-level agent entry point for Codex and other agents.

#### Scenario: New agent lands in the repository root

- **WHEN** an agent reads the root `AGENTS.md`
- **THEN** the file MUST identify this repository as the template source for generated 1C repositories rather than as a business application
- **AND** it MUST point to the authoritative docs index, architecture guide, and verification runbook
- **AND** it MUST keep deep operational detail in linked documents instead of duplicating it inline

### Requirement: Agent Documentation System Of Record

The repository SHALL maintain a single agent-facing documentation index and authoritative runbooks for understanding, operating, and reviewing the template.

#### Scenario: Agent needs authoritative guidance

- **WHEN** an agent asks what the project is, how it is structured, where entrypoints live, how to verify changes, or how to review changes
- **THEN** `docs/agent/index.md` MUST map each of those questions to an authoritative document path
- **AND** the authoritative set MUST include an architecture guide, a template-source-vs-generated-project guide, a verification runbook, a review guide, and an execution-plan guide
- **AND** durable documentation MUST use file-level or section-level links as the primary navigation mechanism rather than line-specific links

### Requirement: Truthful Machine-Readable Agent Context

The repository SHALL keep live automation context truthful for the template source repo and separate any generated-project skeleton context into clearly template-scoped artifacts.

#### Scenario: Agent inspects live automation context

- **WHEN** an agent opens files under the live `automation/context/` surface in the template source repo
- **THEN** those files MUST describe the current repository rather than a future generated project
- **AND** they MUST NOT contain unresolved template placeholders or instructions telling the reader to update the file after project creation
- **AND** generated-project skeleton context, if shipped by the template, MUST be stored under clearly template-scoped filenames or directories so agents can distinguish it from live source-repo context

#### Scenario: Context artifacts are refreshed

- **WHEN** the repository regenerates agent context
- **THEN** the repo-owned export path MUST refresh the live context artifacts deterministically
- **AND** the refresh flow MUST provide a machine-checkable signal that checked-in context is current

### Requirement: Agent Verification Runbook

The repository SHALL provide a documented, dependency-light verification path for first-pass agent work.

#### Scenario: New agent wants a quick baseline

- **WHEN** an agent needs to verify onboarding assumptions or a documentation/tooling change
- **THEN** the repository MUST provide a documented repo-owned baseline command or target for agent verification
- **AND** that baseline MUST avoid requiring a licensed 1C runtime and optional heavyweight analyzers such as BSL LS/Java
- **AND** the verification runbook MUST explain which deeper contours remain outside the baseline and when to use them

### Requirement: Versioned Execution Plans For Long-Running Agent Work

The repository SHALL provide a versioned home for execution plans that span long-running or cross-cutting agent work.

#### Scenario: Work exceeds one short session

- **WHEN** a task spans multiple sessions, needs handoff, or touches multiple major repository zones
- **THEN** the repository MUST provide a checked-in execution-plan location with usage rules and lifecycle states
- **AND** the agent documentation index MUST link to that location as the canonical place for long-running plan artifacts
