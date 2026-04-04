---
name: db-update
description: Импортированный compatibility skill из cc-1c-skills. Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg
argument-hint: [database]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-update

Repo script: `./scripts/skills/run-imported-skill.sh db-update`

## Use When

- Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-update --help
./scripts/skills/run-imported-skill.sh db-update ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-update/SKILL.md`
- Runtime kind: `native-alias`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Для native runner-agnostic workflow предпочитайте: `1c-update-db`.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
