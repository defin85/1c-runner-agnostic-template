---
name: subsystem-validate
description: Импортированный compatibility skill из `cc-1c-skills`: Валидация подсистемы 1С. Используй после создания или модификации подсистемы для проверки корректности
metadata:
  short-description: Валидация подсистемы 1С. Используй после создания или модификации подси…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: subsystem-validate

Repo script: `./scripts/skills/run-imported-skill.sh subsystem-validate`

## Use When

- Валидация подсистемы 1С. Используй после создания или модификации подсистемы для проверки корректности
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh subsystem-validate --help
./scripts/skills/run-imported-skill.sh subsystem-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/subsystem-validate/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
