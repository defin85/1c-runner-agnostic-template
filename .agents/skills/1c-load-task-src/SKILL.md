---
name: 1c-load-task-src
description: Используйте, когда нужно загрузить в ИБ уже закомиченные изменения задачи через repo-owned task bridge.
metadata:
  short-description: Загрузка task-scoped изменений в ИБ.
---

# Agent Skill: 1c-load-task-src

Repo script: `./scripts/platform/load-task-src.sh`

## Use When

- Нужно загрузить в информационную базу уже закомиченные изменения конкретной задачи внутри `src/cf`.
- Нужен repo-owned bridge от commit trailers `Bead:` / `Work-Item:` или explicit `--range` к `load-src --files`.
- Нужны machine-readable wrapper artifacts и delegated `load-src` summary.

## Usage

```bash
./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1
./scripts/platform/load-task-src.sh --profile env/local.json --work-item 93984 --run-root /tmp/load-task-src-run
./scripts/platform/load-task-src.sh --profile env/local.json --range HEAD~2..HEAD --dry-run
```

## Rules

- Не собирайте вручную `git log -> changed files -> --files`; используйте repo script.
- Для canonical trailer block используйте `./scripts/git/task-trailers.sh render --bead <id> --work-item <id>`.
- Сначала читайте wrapper `summary.json`, затем delegated `load-src` artifacts.
