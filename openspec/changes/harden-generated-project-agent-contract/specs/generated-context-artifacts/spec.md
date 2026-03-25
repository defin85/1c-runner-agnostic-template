## MODIFIED Requirements

### Requirement: Generated Metadata Captures Critical Identity And Entrypoints

Шаблон MUST отдавать пригодные к действию generated metadata и компактное onboarding-oriented summary, а не заставлять первый час работы идти только через raw inventory.

#### Scenario: Generated repo contains a configuration XML

- **WHEN** generated repository содержит `src/cf/Configuration.xml`
- **THEN** `automation/context/metadata-index.generated.json` ДОЛЖЕН заполнять identity конфигурации из содержимого XML
- **AND** metadata ДОЛЖНА включать entrypoint-oriented inventory как минимум для configuration roots, web или HTTP services при их наличии, scheduled jobs при их наличии и других high-signal категорий, которые помогают агенту сузить search space
- **AND** export flow ДОЛЖЕН генерировать compact summary artifact с identity, freshness metadata, high-signal counts и hot-path routing hints, подходящими для first-hour onboarding

### Requirement: Semantic Agent Surface Verification

Шаблон MUST механически отклонять drift в generated-repo agent surface, который меняет onboarding truth, утекает private artifacts, рекламирует false-positive verification или оставляет compact onboarding artifacts stale.

#### Scenario: Generated repo drifts to source-centric or leaky guidance

- **WHEN** generated repo docs или derived context маршрутизируют агента в source-repo-centric onboarding, утекают `local-private` artifacts, оставляют critical identity fields пустыми, требуют unconditional `git push` в repo без remote или расходятся с compact onboarding summary
- **THEN** `scripts/qa/check-agent-docs.sh` и релевантные fixture smoke tests ДОЛЖНЫ падать
- **AND** reported failure ДОЛЖЕН явно показывать, какой semantic contract drifted

#### Scenario: Generated repo keeps placeholder verification in a sanctioned contour

- **WHEN** generated repository всё ещё рекламирует `smoke`, `xunit` или `bdd` через sanctioned checked-in contour, но underlying command остаётся placeholder или эквивалентным no-op success path
- **THEN** semantic checks ДОЛЖНЫ падать
- **AND** generated docs и machine-readable artifacts НЕ ДОЛЖНЫ описывать такой contour как baseline-ready
