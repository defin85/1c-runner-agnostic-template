---
name: web-stop
description: Импортированный compatibility skill из `cc-1c-skills`: Остановка Apache HTTP Server. Используй когда пользователь просит остановить веб-сервер, Apache, прекратить веб-публикацию
metadata:
  short-description: Остановка Apache HTTP Server. Используй когда пользователь просит остан…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: web-stop

Repo script: `./scripts/skills/run-imported-skill.sh web-stop`

## Use When

- Остановка Apache HTTP Server. Используй когда пользователь просит остановить веб-сервер, Apache, прекратить веб-публикацию
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-stop --help
./scripts/skills/run-imported-skill.sh web-stop ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-stop/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
