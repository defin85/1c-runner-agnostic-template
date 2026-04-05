---
name: epf-bsp-add-command
description: "Импортированный compatibility skill из `cc-1c-skills`: Добавить команду в дополнительную обработку БСП"
metadata:
  short-description: "Добавить команду в дополнительную обработку БСП"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: epf-bsp-add-command

Repo script: `./scripts/skills/run-imported-skill.sh epf-bsp-add-command`

## Use When

- Добавить команду в дополнительную обработку БСП
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-bsp-add-command --help
./scripts/skills/run-imported-skill.sh epf-bsp-add-command ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-bsp-add-command/SKILL.md`
- Runtime kind: `reference`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
