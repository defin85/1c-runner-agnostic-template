## MODIFIED Requirements

### Requirement: Agent-Facing Ownership Verification

The template SHALL provide static or fixture-level checks that keep generated-project agent-facing artifacts aligned with the documented ownership model.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** template docs, bootstrap hooks, context seeds, export tooling, or template-maintenance workflow change
- **THEN** the relevant static or fixture contours MUST validate generated-project ownership boundaries and freshness expectations
- **AND** those checks MUST detect raw placeholder drift in generated-project-seeded agent context
- **AND** any workflow advertised as a canonical template-maintenance path for generated repositories MUST execute successfully in fixture smoke or stop being advertised as guaranteed-safe

#### Scenario: Template source release workflow changes

- **WHEN** source-repo docs, release scripts, or hook guardrails change the canonical template release path
- **THEN** the static or fixture contours MUST validate that the advertised release command, hook behavior, and documented source release runbook stay consistent
- **AND** the relevant smoke contour MUST prove that accidental overlay tag pushes fail closed while the canonical guarded release path still succeeds
