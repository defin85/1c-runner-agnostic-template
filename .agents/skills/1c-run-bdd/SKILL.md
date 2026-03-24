---
name: 1c-run-bdd
description: Используйте, когда нужно прогнать BDD или acceptance contour через канонический test entrypoint проекта.
metadata:
  short-description: BDD contour.
---

# Agent Skill: 1c-run-bdd

Repo script: `./scripts/test/run-bdd.sh`

## Use When

- Нужно прогнать acceptance или BDD contour.
- Нужен единый adapter-aware запуск с machine-readable артефактами.

## Usage

```bash
./scripts/test/run-bdd.sh --profile env/local.json
./scripts/test/run-bdd.sh --profile env/ci.json --run-root /tmp/run-bdd
./scripts/test/run-bdd.sh --profile env/local.json --dry-run
```

## Rules

- Skill описывает intent и entrypoint, но не дублирует test runtime logic.
- Основной результат смотрите в `summary.json`.
