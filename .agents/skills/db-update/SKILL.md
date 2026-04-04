---
name: db-update
description: Импортированный compatibility skill из `cc-1c-skills`: Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg
metadata:
  short-description: Обновление конфигурации базы данных 1С. Используй когда пользователь пр…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-update

Repo script: `./scripts/skills/run-imported-skill.sh db-update`

## Use When

- Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

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

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
