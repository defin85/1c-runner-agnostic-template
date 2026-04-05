---
name: form-remove
description: "Импортированный compatibility skill из `cc-1c-skills`: Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и др.)"
metadata:
  short-description: "Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и д…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: form-remove

Repo script: `./scripts/skills/run-imported-skill.sh form-remove`

## Use When

- Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и др.)
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-remove --help
./scripts/skills/run-imported-skill.sh form-remove ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-remove/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
