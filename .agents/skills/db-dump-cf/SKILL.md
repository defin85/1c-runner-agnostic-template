---
name: db-dump-cf
description: Импортированный compatibility skill из `cc-1c-skills`: Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит выгрузить конфигурацию в CF, сохранить конфигурацию, сделать бэкап CF
metadata:
  short-description: Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-dump-cf

Repo script: `./scripts/skills/run-imported-skill.sh db-dump-cf`

## Use When

- Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит выгрузить конфигурацию в CF, сохранить конфигурацию, сделать бэкап CF
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-dump-cf --help
./scripts/skills/run-imported-skill.sh db-dump-cf ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-dump-cf/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
