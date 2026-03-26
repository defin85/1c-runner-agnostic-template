# generated-runtime-support-matrix Specification

## Purpose
TBD - created by archiving change unify-generated-project-onboarding-truth. Update Purpose after archive.
## Requirements
### Requirement: Project-Owned Runtime Support Matrix

The template SHALL seed a project-owned runtime support matrix for generated repositories.

#### Scenario: Generated repository receives initial agent-facing context

- **WHEN** `copier copy` creates a generated repository or a template update refreshes generated-project scaffolding
- **THEN** the repository MUST include checked-in runtime support matrix artifacts in machine-readable and human-readable form
- **AND** the machine-readable artifact MUST live at `automation/context/runtime-support-matrix.json`
- **AND** the human-readable companion MUST live at `automation/context/runtime-support-matrix.md`
- **AND** the matrix MUST classify each documented runtime contour at least as `supported`, `unsupported`, `operator-local`, or `provisioned`

### Requirement: Runtime Support Matrix Drives Generated Onboarding

The runtime support matrix SHALL be the canonical checked-in runtime truth for generated-project onboarding.

#### Scenario: Agent asks what can be run in this repository

- **WHEN** an agent needs to know which runtime contours are baseline-safe, unsupported, operator-local, or provisioned
- **THEN** the generated onboarding router and read-only onboarding command MUST point to the runtime support matrix instead of inferring support only from ignored local profiles
- **AND** each matrix entry MUST include the contour identifier, status, expected profile provenance, and canonical runbook or entrypoint
- **AND** operator-local contours MUST remain visible to the agent without being misrepresented as shared baseline-ready checks

### Requirement: Runtime Support Matrix Freshness

The template SHALL keep runtime support matrix artifacts fresh and consistent with adjacent generated-project truth surfaces.

#### Scenario: Runtime support truth changes

- **WHEN** sanctioned runtime profiles, project map entrypoints, verification docs, or onboarding routes change in a generated repository
- **THEN** the repository checks MUST fail if the runtime support matrix is stale or inconsistent with those surfaces
- **AND** the failure MUST identify which contour or supporting artifact no longer matches the matrix

