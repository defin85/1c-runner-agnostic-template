---
name: cfe-validate
description: Импортированный compatibility skill из `cc-1c-skills`: Валидация расширения конфигурации 1С (CFE). Используй после создания или модификации расширения для проверки корректности
metadata:
  short-description: Валидация расширения конфигурации 1С (CFE). Используй после создания ил…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: cfe-validate

Repo script: `./scripts/skills/run-imported-skill.sh cfe-validate`

## Use When

- Валидация расширения конфигурации 1С (CFE). Используй после создания или модификации расширения для проверки корректности
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-validate --help
./scripts/skills/run-imported-skill.sh cfe-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-validate/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
