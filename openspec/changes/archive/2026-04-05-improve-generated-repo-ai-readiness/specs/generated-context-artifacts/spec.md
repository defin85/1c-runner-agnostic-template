## MODIFIED Requirements

### Requirement: Generated Metadata Captures Critical Identity And Entrypoints

Шаблон MUST отдавать пригодные к действию generated metadata, compact onboarding-oriented summaries и project-aware workflow hints, а не заставлять первый час работы идти только через raw inventory.

#### Scenario: Generated repo contains a configuration XML

- **WHEN** generated repository содержит `src/cf/Configuration.xml`
- **THEN** `automation/context/metadata-index.generated.json` ДОЛЖЕН заполнять identity конфигурации из содержимого XML
- **AND** metadata ДОЛЖНА включать entrypoint-oriented inventory как минимум для configuration roots, web или HTTP services при их наличии, scheduled jobs при их наличии и других high-signal категорий, которые помогают агенту сузить search space
- **AND** export flow ДОЛЖЕН генерировать compact summary artifact с identity, freshness metadata, high-signal counts и hot-path routing hints, подходящими для first-hour onboarding
- **AND** export flow ДОЛЖЕН уметь генерировать отдельный generated-derived artifact с compact project-aware recommended skills or workflows, основанный на текущем repo shape и available inventories
- **AND** generated-derived onboarding layer ДОЛЖЕН уметь дополнительно маршрутизировать к отдельному project-delta artifact, если generated repo объявил project-specific delta hints

## ADDED Requirements

### Requirement: Generated Skill Recommendation Artifact

The template SHALL provide a refreshable generated-derived recommendation artifact for first-hour skill selection in generated repositories.

#### Scenario: Generated repo refreshes derived context

- **WHEN** `./scripts/llm/export-context.sh --write` runs in a generated repository
- **THEN** the export flow MUST refresh a generated-derived artifact that maps current repository shape to a compact subset of recommended native or imported skills
- **AND** that artifact MUST stay clearly marked as generated-derived rather than as project-owned truth
- **AND** `--check` or equivalent freshness verification MUST be able to detect if the checked-in recommendation artifact is stale
