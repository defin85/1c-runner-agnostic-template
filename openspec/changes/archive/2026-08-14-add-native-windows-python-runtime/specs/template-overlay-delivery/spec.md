## ADDED Requirements

### Requirement: Python Runtime Overlay Migration

The source template SHALL deliver the Python-first runtime, schema migration tools, thin launchers, generated documentation, and verification contracts through one versioned overlay release.

#### Scenario: Existing generated project consumes the release

- **WHEN** a generated project applies the release through the repo-owned template update path
- **THEN** template-managed runtime files and generated templates MUST update together
- **AND** project-owned files outside managed blocks, local-private profiles, secrets, and deployable `src/**` MUST remain unchanged

#### Scenario: Generated fixture validates migration delivery

- **WHEN** source-template CI materializes and updates a generated-project fixture
- **THEN** the fixture MUST receive schemaVersion 3 examples, Python-first launchers, migration tooling, and platform-aware runtime matrix templates
- **AND** the fixture MUST pass native Windows and Linux contract entrypoints without requiring WSL for Windows-native capabilities

