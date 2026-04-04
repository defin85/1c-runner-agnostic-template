---
name: subsystem-compile
description: Импортированный compatibility skill из `cc-1c-skills`: Создать подсистему 1С — XML-исходники из JSON-определения. Используй когда пользователь просит добавить подсистему (раздел) в конфигурацию
metadata:
  short-description: Создать подсистему 1С — XML-исходники из JSON-определения. Используй ко…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: subsystem-compile

Repo script: `./scripts/skills/run-imported-skill.sh subsystem-compile`

## Use When

- Создать подсистему 1С — XML-исходники из JSON-определения. Используй когда пользователь просит добавить подсистему (раздел) в конфигурацию
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh subsystem-compile --help
./scripts/skills/run-imported-skill.sh subsystem-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/subsystem-compile/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
