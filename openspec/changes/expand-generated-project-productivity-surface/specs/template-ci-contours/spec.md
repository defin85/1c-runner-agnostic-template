## MODIFIED Requirements

### Requirement: Agent-Facing Artifact Freshness

Static CI contour MUST проверять integrity, freshness и semantic truthfulness agent-facing documentation, context и verification guidance.

#### Scenario: Agent-facing artifacts drift

- **WHEN** root agent instructions, agent docs index/runbooks, live automation context, repo-local skill packaging, generated onboarding summaries или generated verification semantics расходятся
- **THEN** static contour ДОЛЖЕН падать до продолжения fixture или runtime contours
- **AND** checks ДОЛЖНЫ выполняться без licensed 1C binaries и secret runtime credentials
- **AND** reported failure ДОЛЖЕН указывать, какой класс artifact-ов stale, inconsistent или semantically misleading
- **AND** curated project-owned truth surfaces, such as architecture maps, runtime quick references, exec-plan starter artifacts, and documented baseline extension slots, MUST be covered by the same freshness contract when they are seeded by the template

### Requirement: Agent-Facing Ownership Verification

The template SHALL provide static or fixture-level checks that keep generated-project agent-facing artifacts aligned with the documented ownership model.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** template docs, bootstrap hooks, context seeds, export tooling, or template-maintenance workflow change
- **THEN** the relevant static or fixture contours MUST validate generated-project ownership boundaries and freshness expectations
- **AND** those checks MUST detect raw placeholder drift in generated-project-seeded agent context
- **AND** any workflow advertised as a canonical template-maintenance path for generated repositories MUST execute successfully in fixture smoke or stop being advertised as guaranteed-safe

#### Scenario: Generated repo advertises project-specific baseline extension

- **WHEN** a generated repository advertises an extra project-owned no-1C baseline smoke or verify target in onboarding docs or read-only onboarding output
- **THEN** the relevant static or fixture contours MUST validate that the advertised target or script exists and is routed as a project-specific extension rather than as template-managed baseline
- **AND** the failure MUST identify the missing or inconsistent extension surface
