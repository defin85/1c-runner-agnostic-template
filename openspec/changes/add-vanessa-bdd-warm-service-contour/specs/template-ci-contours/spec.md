## ADDED Requirements
### Requirement: Vanessa BDD Warm-Service Fixture Contract
The template SHALL provide fixture-level checks for the reusable Vanessa BDD warm-service contour.

#### Scenario: Warm-service contour is not project-configured
- **WHEN** the generated repository has not supplied Vanessa Automation Single, warmup feature, and project extension scope
- **THEN** `bdd-warm-service` lifecycle entrypoints for `up`, `status`, `run`, and `down` MUST fail closed before launching a real 1C runtime when required project-owned inputs are missing
- **AND** the failure MUST write a machine-readable run-root summary containing `status`, `classification`, `message`, `missing_inputs`, and non-secret profile/target metadata
- **AND** the failure MUST explain which project-owned input is missing

#### Scenario: Applied-project values are accidentally copied
- **WHEN** reusable Vanessa BDD warm-service code is rendered into a generated repository
- **THEN** fixture checks MUST fail if generated artifacts contain applied-project infobase names, local user paths, extension defaults, or business scenario names from the source project
- **AND** the audit MUST cover scripts, generated-project docs, generated runtime matrices, fixture templates, and example profiles
- **AND** any remaining match MUST be explicitly justified as non-generated historical context
