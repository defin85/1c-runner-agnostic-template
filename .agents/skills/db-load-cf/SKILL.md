---
name: db-load-cf
description: Импортированный compatibility skill из `cc-1c-skills`: Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF
metadata:
  short-description: Загрузка конфигурации 1С из CF-файла. Используй когда пользователь прос…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-load-cf

Repo script: `./scripts/skills/run-imported-skill.sh db-load-cf`

## Use When

- Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-load-cf --help
./scripts/skills/run-imported-skill.sh db-load-cf ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-load-cf/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
