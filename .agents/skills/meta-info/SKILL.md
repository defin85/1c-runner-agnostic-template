---
name: meta-info
description: Импортированный compatibility skill из `cc-1c-skills`: Анализ структуры объекта метаданных 1С из XML-выгрузки — реквизиты, табличные части, формы, движения, типы. Используй для изучения структуры объектов (вместо чтения XML-файлов напрямую) и как подготовительный шаг при написании запросов и кода, работающего с объектами
metadata:
  short-description: Анализ структуры объекта метаданных 1С из XML-выгрузки — реквизиты, таб…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: meta-info

Repo script: `./scripts/skills/run-imported-skill.sh meta-info`

## Use When

- Анализ структуры объекта метаданных 1С из XML-выгрузки — реквизиты, табличные части, формы, движения, типы. Используй для изучения структуры объектов (вместо чтения XML-файлов напрямую) и как подготовительный шаг при написании запросов и кода, работающего с объектами
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh meta-info --help
./scripts/skills/run-imported-skill.sh meta-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/meta-info/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
