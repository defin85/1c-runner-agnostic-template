---
name: role-compile
description: Импортированный compatibility skill из `cc-1c-skills`: Создание роли 1С из описания прав. Используй когда нужно создать новую роль с набором прав на объекты
metadata:
  short-description: Создание роли 1С из описания прав. Используй когда нужно создать новую…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: role-compile

Repo script: `./scripts/skills/run-imported-skill.sh role-compile`

## Use When

- Создание роли 1С из описания прав. Используй когда нужно создать новую роль с набором прав на объекты
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh role-compile --help
./scripts/skills/run-imported-skill.sh role-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/role-compile/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
