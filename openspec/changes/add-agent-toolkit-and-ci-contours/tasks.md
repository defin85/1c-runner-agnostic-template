## 1. Runtime Script Contract

- [x] 1.1 Зафиксировать canonical runtime profile format для generated projects и описать source-of-truth файлы окружения.
- [x] 1.2 Добавить/обновить platform entrypoint’ы для create/load/dump/update/run/diff/publish операций.
- [x] 1.3 Ввести единый artifact contract для capability-скриптов: `run-root`, `summary.json`, сырые логи, fail-closed exit codes.
- [x] 1.4 Добавить shell fixture tests для runtime/diagnostic слоя без требования реальной 1С-платформы.

## 2. Project-Scoped Skills

- [x] 2.1 Добавить project-scoped skills для типовых agent operations в generated projects.
- [x] 2.2 Сделать skills thin-wrapper’ами над repo-owned scripts без дублирования runtime-логики в `SKILL.md`.
- [x] 2.3 Зафиксировать mapping `user intent -> skill -> script entrypoint`.
- [x] 2.4 Добавить документацию по установке, update и ограничениям project-scoped skills.

## 3. CI Contours

- [x] 3.1 Добавить template-level CI для smoke, shell syntax, fixture tests и copier/update regressions.
- [x] 3.2 Добавить generated-project CI template с контурами `static`, `fixture`, `runtime`.
- [x] 3.3 Отдельно описать, что `runtime` jobs запускаются только на self-hosted runners с 1С и не являются обязательным контуром для каждого PR в shared среде.
- [x] 3.4 Добавить документацию по безопасному запуску runtime contour и хранению секретов вне репозитория.

## 4. Delivery And Docs

- [x] 4.1 Обновить `README.md` и agent overlays под новый toolkit contract, не дублируя правила во втором root-level policy файле.
- [x] 4.2 Обновить traceability для всех обязательных требований этого change.
- [x] 4.3 Прогнать `openspec validate --strict --no-interactive` и релевантные smoke checks.
