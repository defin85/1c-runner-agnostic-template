---
name: 1c-run-smoke
description: >
  Этот скилл MUST быть вызван, когда пользователь просит запустить smoke-контур
  через канонический test entrypoint проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-run-smoke

Repo script: `./scripts/test/run-smoke.sh`

## Use When

- Нужно быстро проверить минимальный рабочий контур.
- Нужен единый smoke entrypoint с machine-readable итогом.

## Usage

```bash
./scripts/test/run-smoke.sh --profile env/local.json
./scripts/test/run-smoke.sh --profile env/ci.json --run-root /tmp/run-smoke
./scripts/test/run-smoke.sh --profile env/local.json --dry-run
```

## Rules

- Не переносить smoke runtime logic в skill.
- Используй `summary.json` как первичный verdict.
