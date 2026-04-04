---
name: db-dump-xml
description: Импортированный compatibility skill из `cc-1c-skills`: Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles
metadata:
  short-description: Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь прос…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-dump-xml

Repo script: `./scripts/skills/run-imported-skill.sh db-dump-xml`

## Use When

- Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-dump-xml --help
./scripts/skills/run-imported-skill.sh db-dump-xml ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-dump-xml/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
