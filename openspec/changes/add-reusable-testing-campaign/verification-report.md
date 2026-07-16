# Отчёт runtime-проверки

Проверка выполнена 2026-07-16 в отдельном чистом Git worktree Delans `/tmp/delans-reusable-testing-gate`; исходное рабочее дерево Delans не изменялось. Временные локальные профили и секреты в отчёт не включены.

## Целевые базы

| Target | Платформа | Конфигурация |
| --- | --- | --- |
| `delans_ut_26_bdd` | `8.3.27.1989` | `11.5.26.118` |
| `delans_unf_bdd` | `8.5.4.1306` | `3.0.13.363` |

Версии подтверждены журналами успешных запусков YAxUnit.

## Команды

Для каждого target последовательно выполнены команды с четырьмя `--extension`: `VATestContour`, `ProjectYAxUnitTests`, `YAxUnit`, `VAExtension`.

```bash
./scripts/platform/check-cfe-config.sh --profile <local-profile> --target <target> --run-root <run-root> --extension VATestContour --extension ProjectYAxUnitTests --extension YAxUnit --extension VAExtension
./scripts/platform/check-cfe-applicability.sh --profile <local-profile> --target <target> --run-root <run-root> --extension VATestContour --extension ProjectYAxUnitTests --extension YAxUnit --extension VAExtension
./scripts/platform/load-cfe.sh --profile <local-profile> --target <target> --run-root <run-root> --extension VATestContour --extension ProjectYAxUnitTests --extension YAxUnit --extension VAExtension
./scripts/test/run-yaxunit.sh --profile <local-profile> --target <target> --run-root <run-root> --extension ProjectYAxUnitTests
ONEC_PROFILE_PATH=<local-profile> ONEC_TARGET_ID=<target> ONEC_BDD_FEATURES=<feature> ONEC_CAPABILITY_RUN_ROOT=<run-root> ./scripts/test/run-bdd-warm-run.sh
```

Поскольку поставляемая заготовка `ProjectYAxUnitTests` намеренно не содержит прикладных тестов, только для runtime gate во временном worktree в неё был добавлен один тривиальный инфраструктурный тест. В шаблон этот тест не переносился.

## Доказательства

| Проверка | УТ | УНФ |
| --- | --- | --- |
| `check-cfe-applicability` | `success`: `/tmp/delans-reusable-gate/ut26-check-applicability-serial2/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-check-applicability-serial2/summary.json` |
| загрузка четырёх расширений | `success`: `/tmp/delans-reusable-gate/ut26-load-2/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-load-2/summary.json` |
| YAxUnit | `success`: `/tmp/delans-reusable-gate/ut26-yax-run-fixture/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-yax-run-fixture-4/summary.json` |
| Vanessa BDD | `success`: `/tmp/delans-reusable-gate/ut26-bdd-run/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-bdd-run/summary.json` |
| `check-cfe-config` | `failed` только для VAExtension: `/tmp/delans-reusable-gate/ut26-check-config-serial2/summary.json` | `failed` только для VAExtension: `/tmp/delans-reusable-gate/unf-check-config-serial2/summary.json` |

`VATestContour`, `ProjectYAxUnitTests` и `YAxUnit` прошли `check-cfe-config` на обоих target. Закреплённый без изменений upstream-снимок VAExtension 1.29 не компилируется для режима `-WebClient`: Designer сообщает недоступные `XMLТипЗнч`, `ПрочитатьJSON` и два отсутствующих обработчика формы. При этом применимость, загрузка и реальные thin-client запуски проходят. Поэтому успешный provisioned-runtime gate, требуемый спецификацией, пока не подтверждён; задача 6.1 остаётся открытой до явного решения по области проверки либо производному патчу VAExtension.
