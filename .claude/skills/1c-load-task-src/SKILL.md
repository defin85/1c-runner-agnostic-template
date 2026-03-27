---
name: 1c-load-task-src
description: >
  Этот скилл MUST быть вызван, когда пользователь просит загрузить в ИБ
  уже закомиченные изменения задачи через repo-owned task bridge.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-load-task-src

Repo script: `./scripts/platform/load-task-src.sh`

## Use When

- Нужно загрузить в ИБ уже закомиченные изменения конкретной задачи внутри `src/cf`.
- Нужен repo-owned bridge от commit trailers `Bead:` / `Work-Item:` или explicit `--range` к `load-src --files`.
- Нужны machine-readable wrapper artifacts и delegated `load-src` summary.

## Usage

```bash
./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1
./scripts/platform/load-task-src.sh --profile env/local.json --work-item 93984 --run-root /tmp/load-task-src-run
./scripts/platform/load-task-src.sh --profile env/local.json --range HEAD~2..HEAD --dry-run
```

## Rules

- Не переносить `git history -> --files` shell logic в `SKILL.md`.
- Для canonical trailer block использовать `./scripts/git/task-trailers.sh render --bead <id> --work-item <id>`.
- Сначала читать wrapper `summary.json`, затем delegated `load-src` artifacts.
