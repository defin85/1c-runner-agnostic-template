---
name: 1c-run-xunit
description: >
  Этот скилл MUST быть вызван, когда пользователь просит запустить xUnit-контур
  через канонический test entrypoint проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-run-xunit

Repo script: `./scripts/test/run-xunit.sh`

## Use When

- Нужно прогнать xUnit/код-level тесты.
- Нужны артефакты прогона и единый adapter-aware интерфейс.

## Usage

```bash
./scripts/test/run-xunit.sh --profile env/local.json
./scripts/test/run-xunit.sh --profile env/ci.json --run-root /tmp/run-xunit
./scripts/test/run-xunit.sh --profile env/local.json --dry-run
```

## Rules

- Не встраивай runtime-команды тестового контура в этот skill.
- Проверяй `summary.json` перед чтением сырых логов.
