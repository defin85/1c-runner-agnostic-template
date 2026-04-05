---
name: interface-edit
description: "Импортированный compatibility skill из cc-1c-skills. Настройка командного интерфейса подсистемы 1С. Используй когда нужно скрыть или показать команды, разместить в группах, настроить порядок"
argument-hint: "<CIPath> <Operation> <Value>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /interface-edit

Repo script: `./scripts/skills/run-imported-skill.sh interface-edit`

## Use When

- Настройка командного интерфейса подсистемы 1С. Используй когда нужно скрыть или показать команды, разместить в группах, настроить порядок
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh interface-edit --help
./scripts/skills/run-imported-skill.sh interface-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/interface-edit/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
