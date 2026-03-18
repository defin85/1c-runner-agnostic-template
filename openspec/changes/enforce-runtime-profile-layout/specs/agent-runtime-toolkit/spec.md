## MODIFIED Requirements

### Requirement: Machine-Readable Runtime Artifacts

Each runtime capability script SHALL produce machine-readable execution artifacts in addition to human-readable logs.

#### Scenario: Agent consumes runtime result

- **WHEN** an agent runs a capability script
- **THEN** the script MUST return a non-zero exit code on failure
- **AND** the run artifacts MUST include a `summary.json`
- **AND** the run artifacts MUST preserve raw logs needed for diagnosis

#### Scenario: Runtime doctor sees non-canonical env layout

- **WHEN** `doctor` inspects a repository whose root `env/` directory contains local `*.json` profiles outside the canonical allowlist and outside `env/.local/`
- **THEN** `doctor` MUST report that layout drift in a machine-readable warning section of `summary.json`
- **AND** the warning MUST identify the unexpected paths and the recommended sandbox location for ad-hoc profiles
- **AND** `doctor` MUST keep overall status successful if all runtime preconditions are otherwise satisfied
