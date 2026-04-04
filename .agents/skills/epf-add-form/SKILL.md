---
name: epf-add-form
description: Импортированный compatibility skill из `cc-1c-skills`: Добавить управляемую форму к внешней обработке 1С
metadata:
  short-description: Добавить управляемую форму к внешней обработке 1С
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: epf-add-form

Repo script: `./scripts/skills/run-imported-skill.sh epf-add-form`

## Use When

- Добавить управляемую форму к внешней обработке 1С
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-add-form --help
./scripts/skills/run-imported-skill.sh epf-add-form ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-add-form/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
