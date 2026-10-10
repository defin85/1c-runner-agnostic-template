# template-overlay-delivery Specification

## Purpose
Define how template changes reach generated repositories: bootstrap through copier copy only, a separately tracked overlay version, overlay apply limited to managed paths that preserves project-owned truth, and an explicit, verified source release process.
## Requirements
### Requirement: Bootstrap Uses Copier Copy Only

The template SHALL use `copier` only for bootstrap of a new generated repository, not for ongoing wrapper-layer updates.

#### Scenario: New project is created from the template

- **WHEN** a repository is generated from the template
- **THEN** `copier copy` MUST remain the bootstrap mechanism
- **AND** the generated repository MUST receive enough checked-in metadata to apply future wrapper overlay releases without `copier update`

### Requirement: Generated Repositories Track Overlay Version Separately

Generated repositories SHALL track the applied wrapper overlay version in a checked-in artifact separate from `.copier-answers.yml`.

#### Scenario: Overlay release is applied

- **WHEN** a generated repository applies a wrapper overlay release
- **THEN** the repository MUST update a checked-in overlay version artifact that identifies the applied template release
- **AND** `.copier-answers.yml` MUST remain bootstrap provenance rather than the primary source of truth for ongoing updates

### Requirement: Overlay Apply Uses Only Managed Paths

Generated repositories SHALL update wrapper-layer files only through an explicit manifest of template-managed paths. Test-tooling templates, pinned vendor-source, dependency manifests and initializer/installers SHALL be template-managed, while materialized `src/cfe/**`, `analysis/testing/**` state and `.artifacts/testing/**` SHALL remain outside automatic overlay application.

#### Scenario: Product source tree churn exists in the target repository

- **WHEN** the generated repository has large or fully replaced contents under `src/**`
- **THEN** the wrapper overlay apply/check flow MUST operate only on manifest-declared template-managed paths
- **AND** the cost and behavior of the apply/check flow MUST not depend on reconciling product source tree history through `copier update`

#### Scenario: Overlay refreshes reusable testing tooling

- **WHEN** a project has already materialized or adapted test extensions and applies a newer overlay
- **THEN** the overlay MUST refresh only test-tooling templates, pinned vendor-source, manifests, commands and docs
- **AND** it MUST NOT initialize, replace or delete materialized `src/cfe` extensions, campaign state or installed local binaries

### Requirement: Overlay Apply Preserves Project-Owned Truth

The generated-repo maintenance path SHALL preserve project-owned artifacts while still refreshing generated entry surfaces and managed overlays.

#### Scenario: Generated repository applies a new overlay release

- **WHEN** `template-update` applies a newer wrapper overlay release
- **THEN** `README.md`, `openspec/project.md`, and `automation/context/project-map.md` MUST remain project-owned outside explicit managed blocks
- **AND** the maintenance path MUST refresh the managed README router, `AGENTS.md` overlay, and generated-derived context artifacts

### Requirement: Overlay Maintenance Path Is Documented And Verified

The template SHALL ship docs and automated checks that describe and verify overlay release maintenance as the default ongoing update path.

#### Scenario: Agent or maintainer follows the documented maintenance path

- **WHEN** a generated repository uses `make template-check-update` or `make template-update`
- **THEN** the documented behavior, scripts, and smoke tests MUST agree on overlay release semantics
- **AND** generated-project docs MUST no longer describe ongoing `copier update` as the primary maintenance path

### Requirement: Source Template Release Publishing Is Explicit

The template source repository SHALL publish overlay release tags only through an explicit repo-owned release workflow.

#### Scenario: Maintainer publishes a new overlay release tag

- **WHEN** the source repository publishes the next template overlay release
- **THEN** it MUST provide a repo-owned release command that validates a clean worktree, current remote-tracking state, and baseline verification before pushing the tag
- **AND** the release workflow MUST create or publish the overlay tag intentionally rather than as a side effect of an ordinary branch push
- **AND** the source repository MUST document that workflow as the canonical source release path

#### Scenario: Maintainer accidentally tries to push an overlay tag

- **WHEN** a maintainer attempts to push `refs/tags/v*` outside the canonical release workflow
- **THEN** a repo-owned hook guardrail MUST fail closed before the remote push completes
- **AND** the failure message MUST point back to the canonical source release command or runbook

### Requirement: Overlay Update Retires Legacy Source-Root Routing Files

Generated repositories SHALL remove retired template-seeded routing docs from deployable `src/cf` during overlay maintenance.

#### Scenario: Generated repo updates from an older template release

- **WHEN** `make template-update` or the repo-owned overlay apply path runs in a generated repository that still contains legacy `src/cf/AGENTS.md` or `src/cf/README.md`
- **THEN** the update path MUST remove those retired files as part of the template migration
- **AND** the cleanup MUST NOT rewrite or sanitize neighboring 1C source files under `src/cf`
- **AND** template-maintenance docs and smoke tests MUST describe and verify that stale files disappear after the update

### Requirement: Python Runtime Overlay Migration

The source template SHALL deliver the Python-first runtime, schema migration tools, thin launchers, generated documentation, and verification contracts through one versioned overlay release.

#### Scenario: Existing generated project consumes the release

- **WHEN** a generated project applies the release through the repo-owned template update path
- **THEN** template-managed runtime files and generated templates MUST update together
- **AND** project-owned files outside managed blocks, local-private profiles, secrets, and deployable `src/**` MUST remain unchanged

#### Scenario: Generated fixture validates migration delivery

- **WHEN** source-template CI materializes and updates a generated-project fixture
- **THEN** the fixture MUST receive schemaVersion 3 examples, Python-first launchers, migration tooling, and platform-aware runtime matrix templates
- **AND** the fixture MUST pass native Windows and Linux contract entrypoints without requiring WSL for Windows-native capabilities

### Requirement: Материализованные необязательные модули остаются project-owned

Overlay MUST обновлять заготовки `automation/optional/<module>/` и template-managed исполняемый код модулей. Overlay MUST NOT изменять пути, созданные командой `make optional-module-init`: профили, сценарии, регламенты, навыки и серверные обёртки модуля, а также кеши и каталоги прогонов.

#### Scenario: Обновление проекта с материализованным модулем

- **WHEN** проект с инициализированным модулем `customer-site-operations` выполняет `make template-update` на версию с изменённой заготовкой
- **THEN** `automation/optional/customer-site-operations/` обновлена, а `infra/site/` и `docs/infra/site/` побайтно не изменены

#### Scenario: Первичное создание проекта

- **WHEN** проект создаётся `copier copy`
- **THEN** заготовки модулей присутствуют в `automation/optional/`, а каталоги `infra/site/` и `migration/kd21/` отсутствуют

### Requirement: Правки проекта в template-managed файлах переносятся до его обновления

Перед `template-update` проекта, который изменял template-managed файлы, шаблон MUST содержать результат сверки этих файлов и путей, которые проект убрал из своего `template-managed-paths.txt`: для каждого решение `перенести`, `обобщить`, `оставить в проекте`, `уже есть` или `вывести` с причиной и коммит проекта, на котором выполнена сверка. Правки, которые остаются в проекте, MUST переноситься в project-owned точки расширения, а не терять при обновлении.

#### Scenario: Сверка перед обновлением проекта-источника

- **WHEN** в проекте-источнике готовится `template-update` на версию шаблона с этим change
- **THEN** каждый расходящийся template-managed файл и каждый удалённый проектом путь имеет запись в инвентаре сверки change
- **AND** файлы, изменённые в проекте после коммита сверки, сверены повторно

### Requirement: Проект добавляет свои цели и проверки через точки расширения

Шаблон MUST предоставлять project-owned точки расширения, которые `template-update` не создаёт, не перезаписывает и не удаляет: `Makefile.project`, `make.project.ps1`, каталог `scripts/qa/agent-verify.d/` и проектные блоки в `.gitignore`, `.gitattributes` и `.contextignore`.

#### Scenario: Обновление проекта с заполненными точками расширения

- **WHEN** в проекте заполнены `Makefile.project`, шаг в `scripts/qa/agent-verify.d/` и проектный блок `.gitignore`, и выполняется `template-update`
- **THEN** эти файлы и строки проектного блока совпадают с состоянием до обновления
- **AND** `make <проектная-цель>` выполняется, а `make agent-verify` запускает проектный шаг после базовых проверок

### Requirement: Проектные цели подключаются через `Makefile.project` и `make.project.ps1`

`Makefile.project` MUST подключаться в конце `Makefile` через `-include`, а `make.project.ps1` MUST подключаться `make.ps1`, если файл есть. Цель проекта с именем цели шаблона MUST приводить к ошибке `make.ps1`.

#### Scenario: Проектная цель совпадает с целью шаблона

- **WHEN** `make.project.ps1` объявляет цель с именем, которое уже есть у цели шаблона
- **THEN** `make.ps1` завершается ошибкой

### Requirement: `agent-verify` выполняет проектные шаги из `scripts/qa/agent-verify.d/`

`agent-verify` после базовых проверок MUST выполнять файлы каталога `scripts/qa/agent-verify.d/` по порядку имён: `*.py` на любой ОС, `*.sh` вне Windows, `*.ps1` на Windows. Первый ненулевой код MUST останавливать проверку с именем шага.

#### Scenario: Проектный шаг завершился ошибкой

- **WHEN** один из файлов `scripts/qa/agent-verify.d/` завершается ненулевым кодом
- **THEN** `agent-verify` останавливается с именем этого шага, а следующие по порядку имён шаги не выполняются

#### Scenario: Шаги для другой ОС

- **WHEN** каталог содержит `*.py`, `*.sh` и `*.ps1`, и `agent-verify` запускается в Windows
- **THEN** выполняются `*.py` и `*.ps1`, а `*.sh` пропускаются

### Requirement: `template-update` переносит проектный блок служебных файлов без изменений

`.gitignore`, `.gitattributes` и `.contextignore` MUST содержать проектный блок между маркерами `# >>> project-owned block` и `# <<< project-owned block`. `template-update` MUST переносить содержимое блока в новую версию файла без изменений, а при повреждённых маркерах MUST останавливаться, не изменяя файл.

#### Scenario: Повреждён маркер проектного блока

- **WHEN** в `.gitignore` проекта есть открывающий маркер проектного блока без закрывающего и выполняется `template-update`
- **THEN** обновление завершается ошибкой с именем файла, и `.gitignore` не изменён

### Requirement: Пути из `template-update-preserve-paths.txt` имеют приоритет над манифестом overlay

Пути из `template-update-preserve-paths.txt` MUST иметь приоритет над манифестом overlay: запись с `/` в конце защищает весь каталог.

#### Scenario: Защищён каталог, который обновляет overlay

- **WHEN** `template-update-preserve-paths.txt` содержит запись каталога с `/` в конце, а манифест overlay включает файлы внутри этого каталога
- **THEN** `template-update` не изменяет файлы этого каталога

### Requirement: Python-конфигурация созданного проекта создаётся один раз и принадлежит проекту

`pyproject.toml`, `uv.lock`, `requirements-dev.txt` и `pyrightconfig.json` MUST попадать в созданный проект при `copier copy` и MUST NOT входить в `template-managed-paths.txt`. `template-update` MUST создавать такой файл только при его отсутствии и MUST NOT перезаписывать существующий.

#### Scenario: Проектная зависимость переживает обновление

- **WHEN** проект добавил зависимость в `pyproject.toml` и `uv.lock` и дополнительный корень в `include` своего `pyrightconfig.json`, затем выполнил `template-update`
- **THEN** зависимость, lock-файл и корень `include` остались без изменений

### Requirement: Проверка типов не допускает ослабления общих правил в проекте

Общие правила типизации MUST лежать в template-managed `scripts/qa/pyright-base.json`, а проектный `pyrightconfig.json` MUST подключать его через `extends`. Проверка типов MUST завершаться ошибкой, если `extends` удалён или указывает на другой файл, режим слабее `standard`, правило отключено или понижено, задан `baselineFile`, версия `ruff`, `basedpyright` или `pytest` ниже требуемой либо `requirements-dev.txt` расходится с `uv.lock`.

#### Scenario: Проект ослабил проверку типов

- **WHEN** в проектном `pyrightconfig.json` задан режим `basic` или удалён `extends`
- **THEN** `make verify-types` завершается с ненулевым кодом и называет нарушенное правило
