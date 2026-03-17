---
name: 1c-load-src
description: >
  Этот скилл MUST быть вызван, когда пользователь просит загрузить исходники
  в информационную базу через канонический runtime contract проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-load-src

Repo script: `./scripts/platform/load-src.sh`

## Use When

- Нужно загрузить исходники конфигурации или расширения в ИБ.
- Нужно выполнить adapter-aware load с machine-readable артефактами.

## Usage

```bash
./scripts/platform/load-src.sh --profile env/local.json
./scripts/platform/load-src.sh --profile env/ci.json --run-root /tmp/load-src-run
./scripts/platform/load-src.sh --profile env/local.json --dry-run
```

## Rules

- Не переносить shell/1C CLI в skill как inline logic.
- После выполнения сначала читать `summary.json`, затем лог-файлы.
