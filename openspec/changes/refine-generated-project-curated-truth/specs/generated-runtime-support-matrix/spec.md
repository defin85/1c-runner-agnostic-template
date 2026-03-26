## MODIFIED Requirements

### Requirement: Runtime Support Matrix Drives Generated Onboarding

The runtime support matrix SHALL be the canonical checked-in runtime truth for generated-project onboarding.

#### Scenario: Agent asks what can be run in this repository

- **WHEN** an agent needs to know which runtime contours are baseline-safe, unsupported, operator-local, or provisioned
- **THEN** the generated onboarding router and read-only onboarding command MUST point to the runtime support matrix instead of inferring support only from ignored local profiles
- **AND** each matrix entry MUST include the contour identifier, status, expected profile provenance, and canonical runbook or entrypoint
- **AND** operator-local contours MUST remain visible to the agent without being misrepresented as shared baseline-ready checks
- **AND** operator-local contours SHOULD be able to route through one project-owned operator-local decision runbook rather than forcing manual navigation across multiple runtime docs

### Requirement: Runtime Support Matrix Freshness

The template SHALL keep runtime support matrix artifacts fresh and consistent with adjacent generated-project truth surfaces.

#### Scenario: Runtime support truth changes

- **WHEN** sanctioned runtime profiles, project map entrypoints, verification docs, onboarding routes, or operator-local runbook paths change in a generated repository
- **THEN** the repository checks MUST fail if the runtime support matrix is stale or inconsistent with those surfaces
- **AND** the failure MUST identify which contour or supporting artifact no longer matches the matrix
