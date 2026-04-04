---
name: cf-init
description: Импортированный compatibility skill из cc-1c-skills. Создать пустую конфигурацию 1С (scaffold XML-исходников). Используй когда нужно начать новую конфигурацию с нуля
argument-hint: <Name> [-Synonym <name>] [-OutputDir src]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cf-init

Repo script: `./scripts/skills/run-imported-skill.sh cf-init`

## Use When

- Создать пустую конфигурацию 1С (scaffold XML-исходников). Используй когда нужно начать новую конфигурацию с нуля
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cf-init --help
./scripts/skills/run-imported-skill.sh cf-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cf-init/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
