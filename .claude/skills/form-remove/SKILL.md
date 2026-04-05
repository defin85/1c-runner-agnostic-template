---
name: form-remove
description: "Импортированный compatibility skill из cc-1c-skills. Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и др.)"
argument-hint: "<ObjectName> <FormName>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /form-remove

Repo script: `./scripts/skills/run-imported-skill.sh form-remove`

## Use When

- Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и др.)
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
