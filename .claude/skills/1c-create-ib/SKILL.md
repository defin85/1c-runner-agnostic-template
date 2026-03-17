---
name: 1c-create-ib
description: >
  Этот скилл MUST быть вызван, когда пользователь просит создать информационную базу
  через канонический runtime contract проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-create-ib

Repo script: `./scripts/platform/create-ib.sh`

## Use When

- Нужно создать новую ИБ.
- Нужен machine-readable результат прогона в `summary.json`.

## Usage

```bash
./scripts/platform/create-ib.sh --profile env/local.json
./scripts/platform/create-ib.sh --profile env/ci.json --run-root /tmp/create-ib-run
./scripts/platform/create-ib.sh --profile env/local.json --dry-run
```

## Rules

- Не дублируй runtime-логику в skill; исполняемый контракт уже находится в repo script.
- После выполнения прочитай `summary.json`, затем при необходимости `stdout.log` и `stderr.log`.
- Если не хватает flags или artifact fields, меняй repo script, а не этот skill.
