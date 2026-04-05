---
name: epf-dump
description: "Импортированный compatibility skill из cc-1c-skills. Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать обработку, получить исходники из EPF/ERF файла"
argument-hint: "<EpfFile>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-dump

Repo script: `./scripts/skills/run-imported-skill.sh epf-dump`

## Use When

- Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать обработку, получить исходники из EPF/ERF файла
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-dump --help
./scripts/skills/run-imported-skill.sh epf-dump ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-dump/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
