## 1. Capability Contract

- [x] 1.1 Зафиксировать, что публичные entrypoint-скрипты `create-ib`, `dump-src`, `load-src` и `update-db` сохраняют прежние пути и intent, а выбор backend переносится во внутренний driver layer.
- [x] 1.2 Зафиксировать per-capability выбор driver для `create-ib`, `dump-src`, `load-src` и `update-db` с default `designer`.
- [x] 1.3 Зафиксировать explicit phase-1 support matrix по capabilities, transport adapters и `ibcmd` connection modes.
- [x] 1.4 Зафиксировать contract для partial/diff-aware loading через `load-src`.

## 2. Runtime Profile And Validation

- [x] 2.1 Добавить в runtime profile structured fields для выбора driver и `ibcmd`-specific connection model.
- [x] 2.2 Зафиксировать canonical XML source-tree contract, совместимый с `ibcmd`.
- [x] 2.3 Зафиксировать обязательные поля и support matrix для `ibcmd` path.
- [x] 2.4 Зафиксировать fail-closed валидацию для неподдерживаемых комбинаций driver/profile/auth/topology/connection-mode.
- [x] 2.5 Зафиксировать precedence rules и запрет на неявное смешивание `driver` с raw `command` override для одной capability.

## 3. Runtime Toolkit Refactor

- [x] 3.1 Разделить внутри toolkit transport adapter и capability driver как две независимые оси выбора.
- [x] 3.2 Добавить builder/dispatcher для `designer` и `ibcmd` реализаций `create-ib`, `dump-src`, `load-src` и `update-db`.
- [x] 3.3 Добавить driver-aware path для partial import of selected configuration files через `load-src`.
- [x] 3.4 Обновить `summary.json` и doctor так, чтобы они отражали выбранный driver и redacted driver-specific context без утечки секретов.

## 4. Verification And Docs

- [x] 4.1 Обновить `README.md`, `env/README.md` и versioned runtime profile examples под новый contract.
- [x] 4.2 Добавить smoke checks для default designer path, ibcmd dispatch, partial import path и fail-closed rejection cases.
- [x] 4.3 Добавить smoke checks для `command xor driver` contract и driver visibility в `summary.json`.
- [x] 4.4 Прогнать `openspec validate --strict --no-interactive` и релевантные smoke/fixture tests.
