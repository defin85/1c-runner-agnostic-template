---
name: role-info
description: "Импортированный compatibility skill из cc-1c-skills. Компактная сводка прав роли 1С из Rights.xml — объекты, права, RLS, шаблоны ограничений. Используй для аудита прав — какие объекты и действия доступны, ограничения RLS"
argument-hint: "<RightsPath>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /role-info

Repo script: `./scripts/skills/run-imported-skill.sh role-info`

## Use When

- Компактная сводка прав роли 1С из Rights.xml — объекты, права, RLS, шаблоны ограничений. Используй для аудита прав — какие объекты и действия доступны, ограничения RLS
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh role-info --help
./scripts/skills/run-imported-skill.sh role-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/role-info/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
