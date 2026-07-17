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
| `check-cfe-applicability` | `success`: `/tmp/delans-reusable-gate/ut26-final-check-applicability/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-final-check-applicability/summary.json` |
| загрузка четырёх расширений | `success`: `/tmp/delans-reusable-gate/ut26-final-load/summary.json` | VATestContour и ProjectYAxUnitTests: `/tmp/delans-reusable-gate/unf-final-load/summary.json`; успешные повторы YAxUnit и VAExtension: `/tmp/delans-reusable-gate/unf-final-load-retry-yax/summary.json`, `/tmp/delans-reusable-gate/unf-final-load-retry-va/summary.json` |
| YAxUnit | `success`: `/tmp/delans-reusable-gate/ut26-yax-run-fixture/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-yax-run-fixture-4/summary.json` |
| Vanessa BDD | `success`: `/tmp/delans-reusable-gate/ut26-bdd-run/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-bdd-run/summary.json` |
| `check-cfe-config` | `success`: `/tmp/delans-reusable-gate/ut26-final-check-config/summary.json` | `success`: `/tmp/delans-reusable-gate/unf-final-check-config/summary.json` |

VAExtension 1.29 поставляется с минимальным производным патчем: вызовы `XMLТипЗнч` и `ПрочитатьJSON` исключены из компиляции WebClient, две команды форм без обработчиков удалены. Исходный и итоговый хеши дерева и перечень отличий зафиксированы в `UPSTREAM.json`. После загрузки патча все четыре расширения прошли `check-cfe-config` и `check-cfe-applicability` на обоих target. На УНФ первая повторная загрузка YAxUnit после успешного импорта вернула общее сообщение `Integrity of configuration structure violated`; отдельный повтор YAxUnit и последующая загрузка VAExtension завершились успешно.
