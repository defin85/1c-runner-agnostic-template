---
name: erf-build
description: Импортированный compatibility skill из cc-1c-skills. Собрать внешний отчёт 1С (ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать отчёт или получить ERF файл из исходников
argument-hint: <ReportName>
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /erf-build

Repo script: `./scripts/skills/run-imported-skill.sh erf-build`

## Use When

- Собрать внешний отчёт 1С (ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать отчёт или получить ERF файл из исходников
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-build --help
./scripts/skills/run-imported-skill.sh erf-build ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-build/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
