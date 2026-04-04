---
name: subsystem-info
description: Импортированный compatibility skill из `cc-1c-skills`: Анализ структуры подсистемы 1С из XML-выгрузки — состав, дочерние подсистемы, командный интерфейс, дерево иерархии. Используй для изучения структуры подсистем и навигации по конфигурации
metadata:
  short-description: Анализ структуры подсистемы 1С из XML-выгрузки — состав, дочерние подси…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: subsystem-info

Repo script: `./scripts/skills/run-imported-skill.sh subsystem-info`

## Use When

- Анализ структуры подсистемы 1С из XML-выгрузки — состав, дочерние подсистемы, командный интерфейс, дерево иерархии. Используй для изучения структуры подсистем и навигации по конфигурации
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh subsystem-info --help
./scripts/skills/run-imported-skill.sh subsystem-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/subsystem-info/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
