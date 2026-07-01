## ADDED Requirements

### Requirement: Warmed BDD Runtime Diagnostics

The template SHALL provide reusable diagnostics for warmed BDD runs without requiring project-specific scenarios.

#### Scenario: BDD feature finishes but runtime logged execution errors

- **WHEN** warmed BDD runner executes a selected feature
- **AND** the runtime profile defines `capabilities.bdd.eventLogDir`
- **THEN** the runner MUST export the event log for the feature execution window
- **AND** it MUST fail the feature when 1C execution errors are present
- **AND** it MUST write event log artifacts under the feature run archive

#### Scenario: Warmed BDD feature uses reusable placeholders

- **WHEN** warmed BDD runner materializes a feature into the warm-service runtime file
- **THEN** it MUST replace the test client port placeholder
- **AND** it MUST replace the fixtures-root placeholder with a project-local or caller-provided fixtures path
- **AND** it MUST use an explicit completion marker rather than treating an intermediate build-status file as final success

### Requirement: PostgreSQL Golden Snapshot Contour

The template SHALL provide a reusable PostgreSQL golden snapshot contour for generated repositories that use DBMS-backed runtime profiles.

#### Scenario: Project restores a PostgreSQL golden snapshot

- **WHEN** `make golden-baseline` uses the template-provided `tests/golden/run.sh`
- **AND** the caller provides a schemaVersion 2 profile with PostgreSQL DBMS infobase fields
- **THEN** the contour MUST restore the configured snapshot into the target database
- **AND** it MUST require DB credentials through the profile's password environment variable
- **AND** it MUST fail closed for missing profile, missing snapshot, unsupported DBMS kind, or unsafe PostgreSQL identifiers

#### Scenario: Project creates a PostgreSQL golden snapshot

- **WHEN** the caller runs the template-provided golden create command with a PostgreSQL DBMS profile
- **THEN** the contour MUST create a custom-format PostgreSQL dump at the selected snapshot path
- **AND** it MUST keep the snapshot under `.artifacts/golden/<target>.dump` by default
