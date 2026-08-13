## MODIFIED Requirements

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

### Requirement: Runtime Support Matrix Freshness

The template SHALL keep runtime support matrix artifacts consistent with generated-project runtime entrypoints, profile policy, platform dimensions, and evidence manifests.

#### Scenario: Runtime support truth changes

- **WHEN** a profile schema, entrypoint, supported platform, evidence class, or runbook changes
- **THEN** repository checks MUST fail on stale JSON or Markdown matrix content
- **AND** the failure MUST identify the mismatching capability/platform entry

#### Scenario: Live evidence is absent or expired

- **WHEN** a live-dependent capability is declared supported without current matching evidence
- **THEN** semantic checks MUST reject the supported status
