---
name: form-edit
description: "Импортированный compatibility skill из cc-1c-skills. Добавление элементов, реквизитов и команд в существующую управляемую форму 1С. Используй когда нужно точечно модифицировать готовую форму"
argument-hint: "<FormPath> <JsonPath>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /form-edit

Repo script: `./scripts/skills/run-imported-skill.sh form-edit`

## Use When

- Добавление элементов, реквизитов и команд в существующую управляемую форму 1С. Используй когда нужно точечно модифицировать готовую форму
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-edit --help
./scripts/skills/run-imported-skill.sh form-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-edit/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
