---
name: subsystem-edit
description: "Импортированный compatibility skill из `cc-1c-skills`: Точечное редактирование подсистемы 1С. Используй когда нужно добавить или удалить объекты из подсистемы, управлять дочерними подсистемами или изменить свойства"
metadata:
  short-description: "Точечное редактирование подсистемы 1С. Используй когда нужно добавить и…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: subsystem-edit

Repo script: `./scripts/skills/run-imported-skill.sh subsystem-edit`

## Use When

- Точечное редактирование подсистемы 1С. Используй когда нужно добавить или удалить объекты из подсистемы, управлять дочерними подсистемами или изменить свойства
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh subsystem-edit --help
./scripts/skills/run-imported-skill.sh subsystem-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/subsystem-edit/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
