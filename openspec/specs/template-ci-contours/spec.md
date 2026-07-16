# template-ci-contours Specification

## Purpose
TBD - created by archiving change add-agent-toolkit-and-ci-contours. Update Purpose after archive.
## Requirements
### Requirement: Layered CI Contours

The template SHALL define separate CI contours for static checks, fixture-level verification, and real 1C runtime execution.

#### Scenario: Template and generated projects run appropriate checks

- **WHEN** CI is configured from the template
- **THEN** it MUST distinguish between checks that can run without a real 1C runtime and checks that require a provisioned runtime environment
- **AND** the static and fixture contours MUST be runnable in ordinary automation environments

### Requirement: Runtime Contour Isolation

The runtime CI contour SHALL be isolated from generic CI environments and explicitly targeted to provisioned 1C infrastructure.

#### Scenario: Runtime jobs avoid unsafe shared execution

- **WHEN** a workflow includes operations that need licensed 1C binaries, real infobases, or secret connection settings
- **THEN** those jobs MUST target self-hosted or equivalently provisioned runners
- **AND** the template MUST document that such jobs are not mandatory for every shared CI execution

### Requirement: Safe Secret Handling

The CI design SHALL avoid storing real runtime credentials or destructive environment details in the template repository.

#### Scenario: Generated project configures runtime jobs

- **WHEN** a generated project enables runtime contour jobs
- **THEN** the repository MUST rely on external secrets or environment configuration for credentials and sensitive connection data
- **AND** the template MUST only ship examples and documentation, not live secrets

### Requirement: Agent-Facing Artifact Freshness

Static CI contour MUST проверять integrity, freshness и semantic truthfulness agent-facing documentation, context и verification guidance.

#### Scenario: Agent-facing artifacts drift

- **WHEN** root agent instructions, agent docs index/runbooks, live automation context, repo-local skill packaging, generated onboarding summaries или generated verification semantics расходятся
- **THEN** static contour ДОЛЖЕН падать до продолжения fixture или runtime contours
- **AND** checks ДОЛЖНЫ выполняться без licensed 1C binaries и secret runtime credentials
- **AND** reported failure ДОЛЖЕН указывать, какой класс artifact-ов stale, inconsistent или semantically misleading
- **AND** curated generated-project surfaces, такие как `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md` и canonical routing между `OpenSpec`, `docs/exec-plans/` и `docs/work-items/`, MUST входить в тот же freshness contract

### Requirement: Agent-Facing Ownership Verification

The template SHALL provide static or fixture-level checks that keep generated-project agent-facing artifacts aligned with the documented ownership model.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** template docs, bootstrap hooks, context seeds, export tooling, template-maintenance workflow, or long-running task routing change
- **THEN** the relevant static or fixture contours MUST validate generated-project ownership boundaries and freshness expectations
- **AND** those checks MUST detect raw placeholder drift in generated-project-seeded agent context
- **AND** any workflow advertised as a canonical template-maintenance path for generated repositories MUST execute successfully in fixture smoke or stop being advertised as guaranteed-safe
- **AND** any new project-owned workspace advertised as the canonical home for long-running task artifacts MUST be proven seedable and routable from generated onboarding docs

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
