---
name: 1c-update-db
description: Используйте, когда нужно применить изменения основной конфигурации к конфигурации базы данных.
metadata:
  short-description: Update DB contour.
---

# Agent Skill: 1c-update-db

Repo script: `./scripts/platform/update-db.sh`

## Use When

- Нужно выполнить `UpdateDBCfg` через канонический script contract.
- Нужно применить изменения после загрузки исходников.

## Usage

```bash
./scripts/platform/update-db.sh --profile env/local.json
./scripts/platform/update-db.sh --profile env/ci.json --run-root /tmp/update-db-run
./scripts/platform/update-db.sh --profile env/local.json --dry-run
```

## Rules

- Skill не должен становиться отдельным runtime implementation.
- Если нужен новый adapter behavior, меняйте repo script.
