# Change: расширить runtime toolkit до ibcmd driver для core capabilities

## Why

Текущий runtime toolkit уже дает стабильные entrypoint-скрипты для `create-ib`, `dump-src`, `load-src` и `update-db`, но их стандартная реализация жестко завязана на `1cv8 DESIGNER` и `CREATEINFOBASE`. Это хорошо работает для существующего контура, но не позволяет использовать `ibcmd` как штатный runtime path там, где он уже поддерживает создание ИБ, выгрузку/загрузку конфигурации и применение изменений к database configuration.

Добавлять второй публичный набор скриптов под `ibcmd` невыгодно: это удвоит документацию, smoke-проверки, CI и agent playbooks, при том что пользовательский intent остается тем же самым. Добавлять `ibcmd` как еще один `runnerAdapter` тоже неверно, потому что `runnerAdapter` сейчас описывает transport/execution path, а `ibcmd` меняет еще и внутренний способ реализации capability.

Отдельная задача в том, что `ibcmd` умеет не только full import/export, но и частичную загрузку конфигурации из выбранных XML-файлов. Этот режим нужен generated projects для controlled diff loading в ИБ и должен быть частью публичного capability contract, а не ad-hoc escape hatch через raw command arrays.

## What Changes

- Ввести отдельную ось `driver` для core runtime capabilities, сохранив публичные entrypoint-скрипты `scripts/platform/create-ib.sh`, `scripts/platform/dump-src.sh`, `scripts/platform/load-src.sh` и `scripts/platform/update-db.sh` без дублирования.
- Зафиксировать минимальный support matrix для phase 1:
  - `designer` остается default driver;
  - `ibcmd` добавляется как optional driver для `create-ib`, `dump-src`, `load-src` и `update-db`;
  - `ibcmd` phase 1 поддерживается только в явно зафиксированном safe contour, а не для всех transport adapters и connection modes.
- Расширить runtime profile так, чтобы выбор driver задавался per-capability, а `ibcmd` использовал собственный structured connection block вместо неявного переиспользования designer-only полей.
- Добавить explicit contract для partial/diff-aware loading через `load-src`, чтобы generated project мог загрузить в ИБ выбранный набор XML-файлов, а не только полную конфигурацию.
- Ввести fail-closed validation для неподдерживаемых комбинаций profile/driver/auth/topology/connection-mode.
- Зафиксировать в machine-readable artifacts, какой driver был выбран для конкретного capability run.

## Out Of Scope

- Добавление второго публичного namespace скриптов вроде `scripts/ibcmd/*`.
- Замена текущего `runnerAdapter` на новый общий execution stack.
- Поддержка всех возможных режимов `ibcmd` с первого шага без explicit support matrix и валидации.
- Расширение `ibcmd` path на `publish-http`, тестовые contour-ы и прочие non-core capabilities.
- Автоматическое выравнивание feature parity для каждого transport adapter; phase 1 может сознательно поддерживать только узкую матрицу adapter/mode combinations.

## Delivery Strategy

1. Зафиксировать capability-first contract: публичные `create-ib`, `dump-src`, `load-src`, `update-db` остаются стабильными, а driver выбирается внутри runtime toolkit.
2. Описать profile additions, canonical XML format contract и phase-1 support matrix для `designer` и `ibcmd`.
3. Реализовать dispatch между transport adapter и capability driver без изменения пользовательского entrypoint contract.
4. Добавить partial/diff-aware `load-src` contract для controlled import of selected XML files.
5. Добавить smoke coverage на default designer path, ibcmd path, partial import path и fail-closed validation.
6. Обновить examples и документацию generated projects.

## Impact

- Affected specs:
  - `ibcmd-capability-drivers`
- Affected code:
  - `scripts/lib/onec.sh`
  - `scripts/lib/runtime-profile.sh`
  - `scripts/lib/capability.sh`
  - `scripts/platform/create-ib.sh`
  - `scripts/platform/dump-src.sh`
  - `scripts/platform/load-src.sh`
  - `scripts/platform/update-db.sh`
  - `scripts/diag/doctor.sh`
  - `env/*.example.json`
  - `env/README.md`
  - `README.md`
  - `tests/smoke/*`
