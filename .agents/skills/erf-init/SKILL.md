---
name: erf-init
description: Импортированный compatibility skill из `cc-1c-skills`: Создать пустой внешний отчёт 1С (scaffold XML-исходников)
metadata:
  short-description: Создать пустой внешний отчёт 1С (scaffold XML-исходников)
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: erf-init

Repo script: `./scripts/skills/run-imported-skill.sh erf-init`

## Use When

- Создать пустой внешний отчёт 1С (scaffold XML-исходников)
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-init --help
./scripts/skills/run-imported-skill.sh erf-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-init/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
