---
name: skd-validate
description: "Импортированный compatibility skill из `cc-1c-skills`: Валидация схемы компоновки данных 1С (СКД). Используй после создания или модификации СКД для проверки корректности"
metadata:
  short-description: "Валидация схемы компоновки данных 1С (СКД). Используй после создания ил…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: skd-validate

Repo script: `./scripts/skills/run-imported-skill.sh skd-validate`

## Use When

- Валидация схемы компоновки данных 1С (СКД). Используй после создания или модификации СКД для проверки корректности
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh skd-validate --help
./scripts/skills/run-imported-skill.sh skd-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/skd-validate/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
