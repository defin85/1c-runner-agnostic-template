---
name: db-list
description: "Импортированный compatibility skill из `cc-1c-skills`: Управление реестром баз данных 1С (.v8-project.json). Используй когда пользователь говорит про базы данных, список баз, \"добавь базу\", \"какие базы есть\""
metadata:
  short-description: "Управление реестром баз данных 1С (.v8-project.json). Используй когда п…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-list

Repo script: `./scripts/skills/run-imported-skill.sh db-list`

## Use When

- Управление реестром баз данных 1С (.v8-project.json). Используй когда пользователь говорит про базы данных, список баз, "добавь базу", "какие базы есть"
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-list --help
./scripts/skills/run-imported-skill.sh db-list ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-list/SKILL.md`
- Runtime kind: `reference`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
