---
name: cfe-init
description: "Импортированный compatibility skill из cc-1c-skills. Создать расширение конфигурации 1С (CFE) — scaffold XML-исходников. Используй когда нужно создать новое расширение для исправления, доработки или дополнения конфигурации"
argument-hint: "<Name> [-ConfigPath <path>] [-Purpose Patch|Customization|AddOn] [-CompatibilityMode Version8_3_24]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cfe-init

Repo script: `./scripts/skills/run-imported-skill.sh cfe-init`

## Use When

- Создать расширение конфигурации 1С (CFE) — scaffold XML-исходников. Используй когда нужно создать новое расширение для исправления, доработки или дополнения конфигурации
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-init --help
./scripts/skills/run-imported-skill.sh cfe-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-init/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
