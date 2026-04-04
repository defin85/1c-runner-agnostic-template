---
name: epf-init
description: Импортированный compatibility skill из cc-1c-skills. Создать пустую внешнюю обработку 1С (scaffold XML-исходников)
argument-hint: <Name> [Synonym]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-init

Repo script: `./scripts/skills/run-imported-skill.sh epf-init`

## Use When

- Создать пустую внешнюю обработку 1С (scaffold XML-исходников)
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-init --help
./scripts/skills/run-imported-skill.sh epf-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-init/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
