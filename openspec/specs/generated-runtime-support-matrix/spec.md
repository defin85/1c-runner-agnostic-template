# generated-runtime-support-matrix Specification

## Purpose
Define the project-owned runtime support matrix that records which runtime contours are supported, operator-local or unsupported, drives generated onboarding, and stays fresh and aligned with the runtime quick reference for every target.
## Requirements
### Requirement: Project-Owned Runtime Support Matrix
The template SHALL seed a project-owned runtime support matrix that records status and evidence requirements for each documented capability/platform pair.

#### Scenario: Generated repository receives initial agent-facing context
- **WHEN** `copier copy` creates a generated repository or an overlay refreshes generated scaffolding
- **THEN** checked-in JSON and Markdown matrix artifacts MUST exist
- **AND** every documented contour MUST use the shared status vocabulary
- **AND** each platform entry MUST declare whether contract-only or contract-plus-live evidence is required
- **AND** operator-local contours MUST not be represented as shared baseline-ready checks

#### Scenario: Live-dependent capability is marked supported

- **WHEN** a capability controls an infobase, operating-system service, HTTP publication, or long-running broker
- **THEN** `supported` MUST require evidence with platform/runtime fingerprint, timestamp, and expiry policy

### Requirement: Runtime Support Matrix Drives Generated Onboarding

The runtime support matrix SHALL be the canonical checked-in runtime truth for generated-project onboarding.

#### Scenario: Agent asks what can be run in this repository

- **WHEN** an agent needs to know which runtime contours are baseline-safe, unsupported, operator-local, or provisioned
- **THEN** the generated onboarding router and read-only onboarding command MUST point to the runtime support matrix instead of inferring support only from ignored local profiles
- **AND** each matrix entry MUST include the contour identifier, status, expected profile provenance, and canonical runbook or entrypoint
- **AND** operator-local contours MUST remain visible to the agent without being misrepresented as shared baseline-ready checks
- **AND** operator-local contours SHOULD be able to route through one project-owned operator-local decision runbook rather than forcing manual navigation across multiple runtime docs

### Requirement: Runtime Support Matrix Freshness

The template SHALL keep runtime support matrix artifacts consistent with generated-project runtime entrypoints, profile policy, platform dimensions, and evidence manifests.

#### Scenario: Runtime support truth changes

- **WHEN** a profile schema, entrypoint, supported platform, evidence class, or runbook changes
- **THEN** repository checks MUST fail on stale JSON or Markdown matrix content
- **AND** the failure MUST identify the mismatching capability/platform entry

#### Scenario: Live evidence is absent or expired

- **WHEN** a live-dependent capability is declared supported without current matching evidence
- **THEN** semantic checks MUST reject the supported status

### Requirement: Runtime Quick Reference Stays Aligned With Matrix
The template SHALL keep a concise runtime quick reference aligned with the project-owned runtime support matrix in generated repositories.

#### Scenario: Generated repo explains runtime status to a new agent
- **WHEN** a generated repository exposes `docs/agent/runtime-quickstart.md`
- **THEN** the quick reference MUST use the same contour identifiers and status vocabulary as `automation/context/runtime-support-matrix.md` and `.json`
- **AND** each quick-reference contour summary MUST point back to the corresponding canonical runbook, entrypoint, or matrix entry
- **AND** the runtime quick reference MUST remain short enough to answer “what can I run here and with what prerequisites?” without requiring the full general-purpose runtime contract first
- **AND** reusable operator-local contours MUST describe their profile or explicit argument prerequisites rather than naming a source-project infobase or publication

### Requirement: Target-Aware Runtime Support Matrix
The runtime support matrix SHALL represent runtime contours that are valid only for selected target configurations.

#### Scenario: Matrix documents target-specific extension checks
- **WHEN** a generated project documents extension load, applicability, config check, update-db, or YAxUnit contours for a multi-target workspace
- **THEN** the matrix entry MUST identify the target ids to which the contour applies
- **AND** the entry MUST list or reference the extension set selected for each target
- **AND** operator-local target profiles MUST remain distinguishable from shared checked-in target metadata

#### Scenario: Matrix and target metadata drift
- **WHEN** a matrix entry references a target id or extension name that no longer exists in project-owned target metadata
- **THEN** semantic checks MUST fail
- **AND** the failure MUST identify the stale target or extension reference

### Requirement: Vanessa BDD Warm-Service Matrix Entry
The template SHALL represent the optional Vanessa BDD warm-service contour in generated-project runtime support artifacts and SHALL identify explicit test-tooling preparation without embedding project-specific defaults.

#### Scenario: Generated repository advertises scenario-testing warm runs
- **WHEN** a generated repository receives or refreshes runtime support matrix artifacts from the template
- **THEN** the matrix MUST include a `bdd-warm-service` contour entry
- **AND** the entry MUST classify the contour as `operator-local` or `unsupported`, not `supported`
- **AND** the entry MUST identify `init-test-tooling` and `install-test-tooling` as explicit prerequisites when their outputs are absent
- **AND** the entry MUST point to a project-owned runbook or entrypoint explaining required local Vanessa inputs: Vanessa Automation Single path, warmup feature path, library paths, step definitions, extension scope, and `operatorLocalTargets.vanessaBdd` target binding
- **AND** the entry MUST NOT include applied-project infobase names, extension names, file paths, or business scenario names
- **AND** the entry MUST NOT claim that bootstrap or overlay update automatically materializes source extensions or downloads Vanessa Automation Single

### Requirement: YAxUnit Runtime Preparation Entry

The generated runtime support matrix SHALL describe YAxUnit and YAxUnit warm RPC as operator-local contours backed by explicit initialization of pinned YAxUnit source and a project-owned tests extension.

#### Scenario: Generated project inspects YAxUnit support

- **WHEN** generated-project runtime support artifacts are rendered or refreshed
- **THEN** the matrix MUST route missing source extensions to `init-test-tooling`
- **AND** it MUST route installed source extensions to the existing `sync-yaxunit-runtime` and YAxUnit entrypoints
- **AND** it MUST distinguish source initialization from synchronization into a selected 1C target
