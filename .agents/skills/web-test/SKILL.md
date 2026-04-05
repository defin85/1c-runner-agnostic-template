---
name: web-test
description: "Импортированный compatibility skill из `cc-1c-skills`: Тестирование 1С через веб-клиент — автоматизация действий в браузере. Используй когда пользователь просит проверить, протестировать, автоматизировать действия в 1С через браузер"
metadata:
  short-description: "Тестирование 1С через веб-клиент — автоматизация действий в браузере. И…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: web-test

Repo script: `./scripts/skills/run-imported-skill.sh web-test`

## Use When

- Тестирование 1С через веб-клиент — автоматизация действий в браузере. Используй когда пользователь просит проверить, протестировать, автоматизировать действия в 1С через браузер
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-test --help
./scripts/skills/run-imported-skill.sh web-test ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-test/SKILL.md`
- Runtime kind: `node`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Node/Playwright helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
