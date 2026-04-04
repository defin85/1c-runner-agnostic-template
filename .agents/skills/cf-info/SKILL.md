---
name: cf-info
description: Импортированный compatibility skill из `cc-1c-skills`: Анализ структуры конфигурации 1С — свойства, состав, счётчики объектов. Используй для обзора конфигурации — какие объекты есть, сколько их, какие настройки
metadata:
  short-description: Анализ структуры конфигурации 1С — свойства, состав, счётчики объектов.…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: cf-info

Repo script: `./scripts/skills/run-imported-skill.sh cf-info`

## Use When

- Анализ структуры конфигурации 1С — свойства, состав, счётчики объектов. Используй для обзора конфигурации — какие объекты есть, сколько их, какие настройки
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cf-info --help
./scripts/skills/run-imported-skill.sh cf-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cf-info/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
