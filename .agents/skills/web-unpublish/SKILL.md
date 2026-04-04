---
name: web-unpublish
description: Импортированный compatibility skill из `cc-1c-skills`: Удаление веб-публикации 1С из Apache. Используй когда пользователь просит убрать публикацию, удалить веб-доступ к базе
metadata:
  short-description: Удаление веб-публикации 1С из Apache. Используй когда пользователь прос…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: web-unpublish

Repo script: `./scripts/skills/run-imported-skill.sh web-unpublish`

## Use When

- Удаление веб-публикации 1С из Apache. Используй когда пользователь просит убрать публикацию, удалить веб-доступ к базе
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-unpublish --help
./scripts/skills/run-imported-skill.sh web-unpublish ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-unpublish/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
