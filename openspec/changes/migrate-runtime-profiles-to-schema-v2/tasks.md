## 1. Schema Contract

- [x] 1.1 Зафиксировать canonical `schemaVersion: 2` runtime profile format для generated projects.
- [x] 1.2 Зафиксировать structured fields для platform, infobase coordinates, auth и optional capability config.
- [x] 1.3 Зафиксировать, что literal secrets не хранятся в versioned runtime profiles и заменяются ссылками на env vars.
- [x] 1.4 Зафиксировать fail-closed поведение для legacy `schemaVersion: 1` profiles.

## 2. Runtime Refactor

- [x] 2.1 Перевести runtime loader с `shellEnv` command blobs на structured profile parsing.
- [x] 2.2 Добавить builders для argv/connection parameters вместо хранения полных shell-команд в профиле.
- [x] 2.3 Обновить launcher scripts и doctor под новый contract.
- [x] 2.4 Зафиксировать redaction policy для summary/diagnostic artifacts.

## 3. Migration

- [x] 3.1 Добавить migration guide для generated projects, обновляющихся с `v0.1.x`.
- [x] 3.2 Добавить helper или skeleton-generator для ручной миграции ignored local profiles.
- [x] 3.3 Явно задокументировать, что `copier update` не переписывает ignored `env/local.json` и аналогичные local-only profiles.
- [x] 3.4 Добавить actionable error messages для legacy profiles с ссылкой на migration path.

## 4. Verification And Docs

- [x] 4.1 Обновить `README.md`, `env/README.md` и CI/runtime docs под новый contract.
- [x] 4.2 Добавить smoke/fixture tests для `schemaVersion: 2` parsing, secret indirection и legacy rejection.
- [x] 4.3 Обновить traceability для всех обязательных требований этого change.
- [x] 4.4 Прогнать `openspec validate --strict --no-interactive` и релевантные smoke checks.
