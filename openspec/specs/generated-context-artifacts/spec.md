# generated-context-artifacts Specification

## Purpose
TBD - created by archiving change tighten-generated-project-agent-surface. Update Purpose after archive.
## Requirements
### Requirement: Privacy-Safe Generated Context Artifacts

The template SHALL generate privacy-safe machine-readable context for generated repositories.

#### Scenario: Generated repo refreshes derived context

- **WHEN** `./scripts/llm/export-context.sh --write` runs in a generated repository
- **THEN** `automation/context/source-tree.generated.txt` MUST exclude `local-private` files and machine-local overrides documented by the ownership model
- **AND** the generated artifacts MUST remain stable under `--check` when no repo-owned or template-managed inputs changed

### Requirement: Generated Metadata Captures Critical Identity And Entrypoints

Шаблон MUST отдавать пригодные к действию generated metadata и компактное onboarding-oriented summary, а не заставлять первый час работы идти только через raw inventory.

#### Scenario: Generated repo contains a configuration XML

- **WHEN** generated repository содержит `src/cf/Configuration.xml`
- **THEN** `automation/context/metadata-index.generated.json` ДОЛЖЕН заполнять identity конфигурации из содержимого XML
- **AND** metadata ДОЛЖНА включать entrypoint-oriented inventory как минимум для configuration roots, web или HTTP services при их наличии, scheduled jobs при их наличии и других high-signal категорий, которые помогают агенту сузить search space
- **AND** export flow ДОЛЖЕН генерировать compact summary artifact с identity, freshness metadata, high-signal counts и hot-path routing hints, подходящими для first-hour onboarding

### Requirement: Semantic Agent Surface Verification

The template SHALL mechanically reject generated-repo agent surface drift that changes onboarding truth, leaks private artifacts, or advertises an impossible closeout path.

#### Scenario: Generated repo drifts to source-centric or leaky guidance

- **WHEN** generated repo docs or derived context route agents to source-repo-centric onboarding, leak `local-private` artifacts, leave critical identity fields empty, or require unconditional `git push` in a repo without a remote
- **THEN** `scripts/qa/check-agent-docs.sh` and the relevant fixture smoke tests MUST fail
- **AND** the reported failure MUST identify which semantic contract drifted

#### Scenario: Generated repo promotes local-private runtime truth as shared baseline

- **WHEN** durable docs, project map, onboarding output, or smoke contracts present `env/local.json` or another ignored local-private runtime profile as canonical shared truth for a contour
- **THEN** the semantic checks MUST fail unless a checked-in runtime support matrix classifies that contour as `operator-local` and points to the corresponding runbook or entrypoint
- **AND** runtime support matrix freshness and consistency with the generated onboarding router MUST be validated mechanically

