## ADDED Requirements
### Requirement: Reusable Operator-Local Runtime Smoke Contracts
The template SHALL provide fixture-level smoke tests for reusable operator-local runtime contours without requiring live 1C binaries.

#### Scenario: New contour uses fake runtime tools
- **WHEN** a reusable runtime contour is added to the template
- **THEN** it MUST have a smoke or fixture contract that runs with fake binaries whenever live 1C is not essential to the contract
- **AND** the test MUST verify run-root summaries, fail-closed behavior, and secret redaction where applicable
- **AND** the test MUST NOT depend on project-specific infobase names, IP addresses, extension names, or local user paths

### Requirement: Project-Specific String Audit
The template SHALL prevent accidental promotion of source-project-specific values into generated projects.

#### Scenario: Template imports code from an applied project
- **WHEN** reusable runtime code is copied from an applied project into the template
- **THEN** smoke or manual verification MUST audit for forbidden strings such as applied-project names, local IP addresses, local home paths, and applied-project extension defaults
- **AND** any remaining match MUST be explicitly justified as archive-only or non-generated historical context

### Requirement: Mandatory Golden Baseline Hook
The template SHALL provide a minimal reproducible golden baseline contour for generated repositories.

#### Scenario: Generated repository has no project golden runner yet
- **WHEN** an agent runs `make golden-baseline` before the project configures golden comparison
- **THEN** the contour MUST fail closed with a non-zero exit code
- **AND** it MUST write a run-root `summary.json` that classifies the result as not configured
- **AND** the generated repository MUST include a starter `tests/golden/README.md` explaining that `tests/golden/run.sh` or `GOLDEN_BASELINE_COMMAND` is the project-owned mandatory comparison hook

#### Scenario: Project supplies a golden comparison command
- **WHEN** `tests/golden/run.sh` exists or an explicit command is provided
- **THEN** the contour MUST execute that project-owned command
- **AND** it MUST propagate the command exit code
- **AND** it MUST write a run-root `summary.json` with the command, logs, status, and classification
