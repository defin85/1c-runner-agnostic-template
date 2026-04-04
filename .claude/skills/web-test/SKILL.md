---
name: web-test
description: Импортированный compatibility skill из cc-1c-skills. Тестирование 1С через веб-клиент — автоматизация действий в браузере. Используй когда пользователь просит проверить, протестировать, автоматизировать действия в 1С через браузер
argument-hint: сценарий на естественном языке
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /web-test

Repo script: `./scripts/skills/run-imported-skill.sh web-test`

## Use When

- Тестирование 1С через веб-клиент — автоматизация действий в браузере. Используй когда пользователь просит проверить, протестировать, автоматизировать действия в 1С через браузер
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-test --help
./scripts/skills/run-imported-skill.sh web-test ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-test/SKILL.md`
- Runtime kind: `node`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Node/Playwright helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
