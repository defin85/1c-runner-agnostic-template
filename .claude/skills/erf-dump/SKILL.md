---
name: erf-dump
description: Импортированный compatibility skill из cc-1c-skills. Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла
argument-hint: <ErfFile>
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /erf-dump

Repo script: `./scripts/skills/run-imported-skill.sh erf-dump`

## Use When

- Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-dump --help
./scripts/skills/run-imported-skill.sh erf-dump ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-dump/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
