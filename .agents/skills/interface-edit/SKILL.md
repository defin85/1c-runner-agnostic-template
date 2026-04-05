---
name: interface-edit
description: "Импортированный compatibility skill из `cc-1c-skills`: Настройка командного интерфейса подсистемы 1С. Используй когда нужно скрыть или показать команды, разместить в группах, настроить порядок"
metadata:
  short-description: "Настройка командного интерфейса подсистемы 1С. Используй когда нужно ск…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: interface-edit

Repo script: `./scripts/skills/run-imported-skill.sh interface-edit`

## Use When

- Настройка командного интерфейса подсистемы 1С. Используй когда нужно скрыть или показать команды, разместить в группах, настроить порядок
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh interface-edit --help
./scripts/skills/run-imported-skill.sh interface-edit ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/interface-edit/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
