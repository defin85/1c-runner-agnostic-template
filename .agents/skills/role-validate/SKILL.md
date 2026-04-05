---
name: role-validate
description: "Импортированный compatibility skill из `cc-1c-skills`: Валидация роли 1С. Используй после создания или модификации роли для проверки корректности"
metadata:
  short-description: "Валидация роли 1С. Используй после создания или модификации роли для пр…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: role-validate

Repo script: `./scripts/skills/run-imported-skill.sh role-validate`

## Use When

- Валидация роли 1С. Используй после создания или модификации роли для проверки корректности
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh role-validate --help
./scripts/skills/run-imported-skill.sh role-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/role-validate/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
