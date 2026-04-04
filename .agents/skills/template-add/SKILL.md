---
name: template-add
description: Импортированный compatibility skill из `cc-1c-skills`: Добавить макет к объекту 1С (обработка, отчёт, справочник, документ и др.)
metadata:
  short-description: Добавить макет к объекту 1С (обработка, отчёт, справочник, документ и д…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: template-add

Repo script: `./scripts/skills/run-imported-skill.sh template-add`

## Use When

- Добавить макет к объекту 1С (обработка, отчёт, справочник, документ и др.)
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh template-add --help
./scripts/skills/run-imported-skill.sh template-add ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/template-add/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
