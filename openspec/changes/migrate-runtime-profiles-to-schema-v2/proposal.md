# Change: перевести runtime profiles на schemaVersion 2 only и ввести явную миграцию

## Why

Текущий runtime profile contract хранит параметры подключения к ИБ косвенно, внутри строковых `*_CMD` переменных в `shellEnv`. Это смешивает topology, authentication, platform paths и shell-quoting в одном слое, плохо валидируется, затрудняет безопасную работу с секретами и делает migration/doctor-проверки слишком хрупкими.

Отдельная проблема в том, что реальные `env/local.json` и `env/ci.json` являются ignored local files. `copier update` не может безопасно переписать их автоматически, поэтому переход на новую схему должен быть оформлен как explicit breaking change с понятной migration story.

## What Changes

- Ввести новый canonical runtime profile contract `schemaVersion: 2` с структурированными блоками для platform, infobase coordinates, authentication и optional runtime contours.
- **BREAKING**: generated projects и launcher scripts должны принимать только `schemaVersion: 2`; `schemaVersion: 1` и `shellEnv`-only profiles больше не поддерживаются.
- Перестать использовать полные shell command strings как source of truth для подключения к ИБ и базовых runtime operations.
- Ввести secret indirection через имена переменных окружения (`passwordEnv` и аналогичные ссылки), а не через literal secrets в versioned JSON.
- Добавить migration guide и helper/skeleton flow для существующих generated projects, потому что ignored local profiles нельзя мигрировать обычным template update.
- Зафиксировать redaction rules: launcher-authored artifacts и summary-файлы не должны содержать resolved secrets или полностью собранные secret-bearing connection strings.

## Out Of Scope

- Поддержка одновременно `schemaVersion: 1` и `schemaVersion: 2`.
- Автоматическое in-place переписывание ignored local files через `copier update`.
- Интеграция с внешними secret managers beyond environment variables.
- Полная замена существующего adapter layer новым transport stack.

## Delivery Strategy

1. Зафиксировать `schemaVersion: 2 only` contract и migration rules в OpenSpec.
2. Реализовать structured profile loader и connection builders вместо `shellEnv` command blobs.
3. Добавить migration guide и helper для владельцев existing generated projects.
4. Обновить examples, doctor, launcher scripts, CI docs и smoke tests.
5. Выпустить breaking template release с новым tag и явными migration instructions.

## Impact

- Affected specs:
  - `runtime-profile-schema`
- Affected code:
  - `scripts/lib/runtime-profile.sh`
  - `scripts/lib/*` builders for infobase connection and platform argv
  - `scripts/platform/*`
  - `scripts/test/*`
  - `scripts/diag/doctor.sh`
  - `env/*.example.json`
  - `env/README.md`
  - `README.md`
  - `docs/migrations/*`
  - `scripts/template/*` or equivalent migration helper path
