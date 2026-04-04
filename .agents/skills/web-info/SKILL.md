---
name: web-info
description: Импортированный compatibility skill из `cc-1c-skills`: Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубликованы, ошибки. Используй когда пользователь спрашивает про статус веб-сервера, опубликованные базы, работает ли Apache
metadata:
  short-description: Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубл…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: web-info

Repo script: `./scripts/skills/run-imported-skill.sh web-info`

## Use When

- Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубликованы, ошибки. Используй когда пользователь спрашивает про статус веб-сервера, опубликованные базы, работает ли Apache
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-info --help
./scripts/skills/run-imported-skill.sh web-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-info/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
