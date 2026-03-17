---
name: 1c-run-bdd
description: >
  Этот скилл MUST быть вызван, когда пользователь просит запустить BDD /
  acceptance-контур через канонический test entrypoint проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-run-bdd

Repo script: `./scripts/test/run-bdd.sh`

## Use When

- Нужно прогнать acceptance или BDD-контур.
- Нужен единый adapter-aware запуск с machine-readable артефактами.

## Usage

```bash
./scripts/test/run-bdd.sh --profile env/local.json
./scripts/test/run-bdd.sh --profile env/ci.json --run-root /tmp/run-bdd
./scripts/test/run-bdd.sh --profile env/local.json --dry-run
```

## Rules

- Skill описывает intent и entrypoint, но не дублирует test runtime logic.
- Основной результат смотреть в `summary.json`.
