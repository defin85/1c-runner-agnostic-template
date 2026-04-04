---
name: db-create
description: Импортированный compatibility skill из `cc-1c-skills`: Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу
metadata:
  short-description: Создание информационной базы 1С. Используй когда пользователь просит со…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-create

Repo script: `./scripts/skills/run-imported-skill.sh db-create`

## Use When

- Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-create --help
./scripts/skills/run-imported-skill.sh db-create ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-create/SKILL.md`
- Runtime kind: `native-alias`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Для native runner-agnostic workflow предпочитайте: `1c-create-ib`.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
