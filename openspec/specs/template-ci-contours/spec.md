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
- **AND** curated generated-project surfaces, такие как `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md` и canonical routing между `OpenSpec`, `bd`, `docs/exec-plans/` и `docs/work-items/`, MUST входить в тот же freshness contract

### Requirement: Agent-Facing Ownership Verification

The template SHALL provide static or fixture-level checks that keep generated-project agent-facing artifacts aligned with the documented ownership model.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** template docs, bootstrap hooks, context seeds, export tooling, template-maintenance workflow, or long-running task routing change
- **THEN** the relevant static or fixture contours MUST validate generated-project ownership boundaries and freshness expectations
- **AND** those checks MUST detect raw placeholder drift in generated-project-seeded agent context
- **AND** any workflow advertised as a canonical template-maintenance path for generated repositories MUST execute successfully in fixture smoke or stop being advertised as guaranteed-safe
- **AND** any new project-owned workspace advertised as the canonical home for long-running task artifacts MUST be proven seedable and routable from generated onboarding docs

