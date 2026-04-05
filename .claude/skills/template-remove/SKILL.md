---
name: template-remove
description: "Импортированный compatibility skill из cc-1c-skills. Удалить макет из объекта 1С (обработка, отчёт, справочник, документ и др.)"
argument-hint: "<ObjectName> <TemplateName>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /template-remove

Repo script: `./scripts/skills/run-imported-skill.sh template-remove`

## Use When

- Удалить макет из объекта 1С (обработка, отчёт, справочник, документ и др.)
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh template-remove --help
./scripts/skills/run-imported-skill.sh template-remove ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/template-remove/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
