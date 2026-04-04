---
name: form-compile
description: Импортированный compatibility skill из cc-1c-skills. Компиляция управляемой формы 1С из компактного JSON-определения. Используй когда нужно создать форму с нуля по описанию элементов
argument-hint: <JsonPath> <OutputPath>
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /form-compile

Repo script: `./scripts/skills/run-imported-skill.sh form-compile`

## Use When

- Компиляция управляемой формы 1С из компактного JSON-определения. Используй когда нужно создать форму с нуля по описанию элементов
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-compile --help
./scripts/skills/run-imported-skill.sh form-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-compile/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
