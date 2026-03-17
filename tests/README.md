# Tests

Каталог автоматизированных проверок.

## Слои

- `xunit/` — code-level TDD
- `smoke/` — короткие инфраструктурные и регрессионные проверки
- `shell-fixtures/` — deterministic shell/runtime fixtures без реальной 1С-платформы
- `fixtures/` — фикстуры и sample-data

## Правило

Для behavior change сначала выбирается подходящий слой проверки:

- детерминированная бизнес-логика -> `tests/xunit`
- инфраструктурный smoke -> `tests/smoke`
- shell/runtime contract -> `tests/shell-fixtures` или узкие smoke-фикстуры
- пользовательский flow -> `features/`

Для runtime profile contract отдельными smoke проверяются:

- `schemaVersion: 2` launchers и summaries
- fail-closed rejection для legacy profiles
- migration helper для existing local profiles
