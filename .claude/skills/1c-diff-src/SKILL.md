---
name: 1c-diff-src
description: >
  Этот скилл MUST быть вызван, когда пользователь просит diff исходников
  или диагностический сравнительный прогон через канонический contract проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-diff-src

Repo script: `./scripts/platform/diff-src.sh`

## Use When

- Нужно сравнить source tree или посмотреть adapter-specific diff.
- Нужен machine-readable результат прогона и единый интерфейс запуска.

## Usage

```bash
./scripts/platform/diff-src.sh --profile env/local.json
./scripts/platform/diff-src.sh --profile env/ci.json --run-root /tmp/diff-src-run
./scripts/platform/diff-src.sh --profile env/local.json --dry-run
```

## Rules

- Не копируй diff-логику в `SKILL.md`.
- Для интерпретации результата начинай с `summary.json`.
