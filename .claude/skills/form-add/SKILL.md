---
name: form-add
description: "Импортированный compatibility skill из cc-1c-skills. Добавить управляемую форму к объекту конфигурации 1С"
argument-hint: "<ObjectPath> <FormName> [Purpose] [--set-default]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /form-add

Repo script: `./scripts/skills/run-imported-skill.sh form-add`

## Use When

- Добавить управляемую форму к объекту конфигурации 1С
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-add --help
./scripts/skills/run-imported-skill.sh form-add ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-add/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
