---
name: 1c-load-diff-src
description: Используйте, когда нужно загрузить в ИБ только текущие git-backed изменения исходников через repo-owned diff bridge.
metadata:
  short-description: Загрузка diff исходников в ИБ.
---

# Agent Skill: 1c-load-diff-src

Repo script: `./scripts/platform/load-diff-src.sh`

## Use When

- Нужно загрузить в информационную базу только текущий diff исходников внутри `src/cf`.
- Нужен repo-owned bridge от git-backed selection к `load-src --files`.
- Нужны machine-readable wrapper artifacts и delegated `load-src` summary.

## Usage

```bash
./scripts/platform/load-diff-src.sh --profile env/local.json
./scripts/platform/load-diff-src.sh --profile env/ci.json --run-root /tmp/load-diff-src-run
./scripts/platform/load-diff-src.sh --profile env/local.json --dry-run
```

## Rules

- Не копируйте inline shell snippet для `git diff -> --files`; используйте repo script.
- Сначала читайте wrapper `summary.json`, затем delegated `load-src` artifacts.
