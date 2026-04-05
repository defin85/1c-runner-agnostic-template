---
name: mxl-decompile
description: "Импортированный compatibility skill из `cc-1c-skills`: Декомпиляция табличного документа (MXL) в JSON-определение. Используй когда нужно получить редактируемое описание существующего макета"
metadata:
  short-description: "Декомпиляция табличного документа (MXL) в JSON-определение. Используй к…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: mxl-decompile

Repo script: `./scripts/skills/run-imported-skill.sh mxl-decompile`

## Use When

- Декомпиляция табличного документа (MXL) в JSON-определение. Используй когда нужно получить редактируемое описание существующего макета
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh mxl-decompile --help
./scripts/skills/run-imported-skill.sh mxl-decompile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/mxl-decompile/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
