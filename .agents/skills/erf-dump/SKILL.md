---
name: erf-dump
description: Импортированный compatibility skill из `cc-1c-skills`: Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла
metadata:
  short-description: Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользоват…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: erf-dump

Repo script: `./scripts/skills/run-imported-skill.sh erf-dump`

## Use When

- Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

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

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
