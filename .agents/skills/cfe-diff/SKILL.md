---
name: cfe-diff
description: Импортированный compatibility skill из `cc-1c-skills`: Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объекты, перехватчики, проверка переноса. Используй когда нужно понять что содержит расширение или проверить перенесены ли вставки в конфигурацию
metadata:
  short-description: Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объект…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: cfe-diff

Repo script: `./scripts/skills/run-imported-skill.sh cfe-diff`

## Use When

- Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объекты, перехватчики, проверка переноса. Используй когда нужно понять что содержит расширение или проверить перенесены ли вставки в конфигурацию
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-diff --help
./scripts/skills/run-imported-skill.sh cfe-diff ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-diff/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
