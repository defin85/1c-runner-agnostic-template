---
name: db-list
description: "Импортированный compatibility skill из cc-1c-skills. Управление реестром баз данных 1С (.v8-project.json). Используй когда пользователь говорит про базы данных, список баз, \"добавь базу\", \"какие базы есть\""
argument-hint: "[add|remove|show]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-list

Repo script: `./scripts/skills/run-imported-skill.sh db-list`

## Use When

- Управление реестром баз данных 1С (.v8-project.json). Используй когда пользователь говорит про базы данных, список баз, "добавь базу", "какие базы есть"
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
