---
name: web-publish
description: Импортированный compatibility skill из `cc-1c-skills`: Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере
metadata:
  short-description: Публикация информационной базы 1С через Apache. Используй когда пользов…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: web-publish

Repo script: `./scripts/skills/run-imported-skill.sh web-publish`

## Use When

- Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-publish --help
./scripts/skills/run-imported-skill.sh web-publish ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-publish/SKILL.md`
- Runtime kind: `native-alias`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Для native runner-agnostic workflow предпочитайте: `1c-publish-http`.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
