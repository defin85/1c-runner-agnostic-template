---
name: form-compile
description: "Импортированный compatibility skill из `cc-1c-skills`: Компиляция управляемой формы 1С из компактного JSON-определения. Используй когда нужно создать форму с нуля по описанию элементов"
metadata:
  short-description: "Компиляция управляемой формы 1С из компактного JSON-определения. Исполь…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: form-compile

Repo script: `./scripts/skills/run-imported-skill.sh form-compile`

## Use When

- Компиляция управляемой формы 1С из компактного JSON-определения. Используй когда нужно создать форму с нуля по описанию элементов
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-compile --help
./scripts/skills/run-imported-skill.sh form-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-compile/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
