---
name: help-add
description: "Импортированный compatibility skill из cc-1c-skills. Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту"
argument-hint: "<ObjectName>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /help-add

Repo script: `./scripts/skills/run-imported-skill.sh help-add`

## Use When

- Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh help-add --help
./scripts/skills/run-imported-skill.sh help-add ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/help-add/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
