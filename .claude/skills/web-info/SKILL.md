---
name: web-info
description: Импортированный compatibility skill из cc-1c-skills. Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубликованы, ошибки. Используй когда пользователь спрашивает про статус веб-сервера, опубликованные базы, работает ли Apache
argument-hint: [args...]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /web-info

Repo script: `./scripts/skills/run-imported-skill.sh web-info`

## Use When

- Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубликованы, ошибки. Используй когда пользователь спрашивает про статус веб-сервера, опубликованные базы, работает ли Apache
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
