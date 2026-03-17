---
name: 1c-dump-src
description: >
  Этот скилл MUST быть вызван, когда пользователь просит выгрузить конфигурацию
  или расширение в исходники через канонический runtime contract проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-dump-src

Repo script: `./scripts/platform/dump-src.sh`

## Use When

- Нужно выгрузить конфигурацию в исходники.
- Нужен repeatable dump через adapter-aware script contract.

## Usage

```bash
./scripts/platform/dump-src.sh --profile env/local.json
./scripts/platform/dump-src.sh --profile env/ci.json --run-root /tmp/dump-src-run
./scripts/platform/dump-src.sh --profile env/local.json --dry-run
```

## Rules

- Не описывай вручную команды платформы внутри skill.
- Проверяй `summary.json` как первичный source of truth по результату выполнения.
