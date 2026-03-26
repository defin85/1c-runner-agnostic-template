## MODIFIED Requirements

### Requirement: Agent Documentation System Of Record

The repository SHALL maintain a single agent-facing documentation index and authoritative runbooks for understanding, operating, and reviewing the template.

#### Scenario: Agent needs authoritative guidance

- **WHEN** an agent asks what the project is, how it is structured, where entrypoints live, how to verify changes, or how to review changes
- **THEN** `docs/agent/index.md` MUST map each of those questions to an authoritative document path
- **AND** the authoritative set MUST include an architecture guide, a template-source-vs-generated-project guide, a verification runbook, a review guide, and an execution-plan guide
- **AND** durable documentation MUST use file-level or section-level links as the primary navigation mechanism rather than line-specific links

#### Scenario: Source maintainer needs the canonical release path

- **WHEN** an agent or maintainer needs to publish a new template overlay release from the source repository
- **THEN** the authoritative docs set MUST include a dedicated source release runbook
- **AND** the docs index or architecture guide MUST route the maintainer there without forcing root `AGENTS.md` to embed the full release manual inline
