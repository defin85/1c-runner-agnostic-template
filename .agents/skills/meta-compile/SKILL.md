---
name: meta-compile
description: Импортированный compatibility skill из `cc-1c-skills`: Создать объект метаданных 1С. Используй когда пользователь просит создать или добавить справочник, документ, регистр, перечисление, константу, общий модуль, обработку, отчёт и др.
metadata:
  short-description: Создать объект метаданных 1С. Используй когда пользователь просит созда…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: meta-compile

Repo script: `./scripts/skills/run-imported-skill.sh meta-compile`

## Use When

- Создать объект метаданных 1С. Используй когда пользователь просит создать или добавить справочник, документ, регистр, перечисление, константу, общий модуль, обработку, отчёт и др.
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh meta-compile --help
./scripts/skills/run-imported-skill.sh meta-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/meta-compile/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
