---
name: skd-edit
description: Импортированный compatibility skill из `cc-1c-skills`: Точечное редактирование схемы компоновки данных 1С (СКД). Используй когда нужно модифицировать существующую СКД — добавить поля, итоги, фильтры, параметры, изменить текст запроса
metadata:
  short-description: Точечное редактирование схемы компоновки данных 1С (СКД). Используй ког…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: skd-edit

Repo script: `./scripts/skills/run-imported-skill.sh skd-edit`

## Use When

- Точечное редактирование схемы компоновки данных 1С (СКД). Используй когда нужно модифицировать существующую СКД — добавить поля, итоги, фильтры, параметры, изменить текст запроса
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh skd-edit --help
./scripts/skills/run-imported-skill.sh skd-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/skd-edit/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
