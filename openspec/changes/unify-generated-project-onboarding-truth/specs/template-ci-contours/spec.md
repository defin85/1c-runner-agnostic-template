## MODIFIED Requirements

### Requirement: Agent-Facing Ownership Verification

The template SHALL provide static or fixture-level checks that keep generated-project agent-facing artifacts aligned with the documented ownership model.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** template docs, bootstrap hooks, context seeds, export tooling, or template-maintenance workflow change
- **THEN** the relevant static or fixture contours MUST validate generated-project ownership boundaries and freshness expectations
- **AND** those checks MUST detect raw placeholder drift in generated-project-seeded agent context
- **AND** any workflow advertised as a canonical template-maintenance path for generated repositories MUST execute successfully in fixture smoke or stop being advertised as guaranteed-safe

#### Scenario: Runtime support truth drifts away from ownership model

- **WHEN** a generated repository advertises runtime contours in project map, verification docs, or onboarding output
- **THEN** the static or fixture contours MUST verify that every advertised contour is represented in the checked-in runtime support matrix with status, provenance, and runbook or entrypoint metadata
- **AND** the checks MUST fail if ignored local-private profiles become durable shared truth without explicit `operator-local` classification
- **AND** the reported failure MUST identify which advertised contour or onboarding surface drifted
