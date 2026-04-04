---
name: form-add
description: Импортированный compatibility skill из `cc-1c-skills`: Добавить управляемую форму к объекту конфигурации 1С
metadata:
  short-description: Добавить управляемую форму к объекту конфигурации 1С
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: form-add

Repo script: `./scripts/skills/run-imported-skill.sh form-add`

## Use When

- Добавить управляемую форму к объекту конфигурации 1С
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-add --help
./scripts/skills/run-imported-skill.sh form-add ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-add/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
