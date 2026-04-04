---
name: img-grid
description: Импортированный compatibility skill из `cc-1c-skills`: Наложить пронумерованную сетку на изображение для определения пропорций колонок
metadata:
  short-description: Наложить пронумерованную сетку на изображение для определения пропорций…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: img-grid

Repo script: `./scripts/skills/run-imported-skill.sh img-grid`

## Use When

- Наложить пронумерованную сетку на изображение для определения пропорций колонок
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh img-grid --help
./scripts/skills/run-imported-skill.sh img-grid ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/img-grid/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
