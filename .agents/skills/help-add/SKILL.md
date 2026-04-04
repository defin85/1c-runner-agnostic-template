---
name: help-add
description: Импортированный compatibility skill из `cc-1c-skills`: Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту
metadata:
  short-description: Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник,…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: help-add

Repo script: `./scripts/skills/run-imported-skill.sh help-add`

## Use When

- Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh help-add --help
./scripts/skills/run-imported-skill.sh help-add ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/help-add/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
