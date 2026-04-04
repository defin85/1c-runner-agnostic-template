---
name: skd-info
description: Импортированный compatibility skill из cc-1c-skills. Анализ структуры схемы компоновки данных 1С (СКД) — наборы, поля, параметры, варианты. Используй для понимания отчёта — источник данных (запрос), доступные поля, параметры
argument-hint: <TemplatePath> [-Mode overview|query|fields|links|calculated|resources|params|variant|templates|trace|full] [-Name <dataset|variant|field|group>]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /skd-info

Repo script: `./scripts/skills/run-imported-skill.sh skd-info`

## Use When

- Анализ структуры схемы компоновки данных 1С (СКД) — наборы, поля, параметры, варианты. Используй для понимания отчёта — источник данных (запрос), доступные поля, параметры
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh skd-info --help
./scripts/skills/run-imported-skill.sh skd-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/skd-info/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
