---
name: skd-edit
description: "Импортированный compatibility skill из cc-1c-skills. Точечное редактирование схемы компоновки данных 1С (СКД). Используй когда нужно модифицировать существующую СКД — добавить поля, итоги, фильтры, параметры, изменить текст запроса"
argument-hint: "<TemplatePath> -Operation <op> -Value <value>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /skd-edit

Repo script: `./scripts/skills/run-imported-skill.sh skd-edit`

## Use When

- Точечное редактирование схемы компоновки данных 1С (СКД). Используй когда нужно модифицировать существующую СКД — добавить поля, итоги, фильтры, параметры, изменить текст запроса
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh skd-edit --help
./scripts/skills/run-imported-skill.sh skd-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/skd-edit/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
