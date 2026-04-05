---
name: epf-add-form
description: "Импортированный compatibility skill из cc-1c-skills. Добавить управляемую форму к внешней обработке 1С"
argument-hint: "<ProcessorName> <FormName> [Synonym]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-add-form

Repo script: `./scripts/skills/run-imported-skill.sh epf-add-form`

## Use When

- Добавить управляемую форму к внешней обработке 1С
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-add-form --help
./scripts/skills/run-imported-skill.sh epf-add-form ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-add-form/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
