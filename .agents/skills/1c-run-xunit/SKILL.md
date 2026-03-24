---
name: 1c-run-xunit
description: Используйте, когда нужно прогнать xUnit contour через канонический test entrypoint проекта.
metadata:
  short-description: xUnit contour.
---

# Agent Skill: 1c-run-xunit

Repo script: `./scripts/test/run-xunit.sh`

## Use When

- Нужно прогнать xUnit или code-level tests.
- Нужны артефакты прогона и единый adapter-aware интерфейс.

## Usage

```bash
./scripts/test/run-xunit.sh --profile env/local.json
./scripts/test/run-xunit.sh --profile env/ci.json --run-root /tmp/run-xunit
./scripts/test/run-xunit.sh --profile env/local.json --dry-run
```

## Rules

- Не встраивайте runtime-команды тестового контура в skill.
- Проверяйте `summary.json` перед чтением сырых логов.
