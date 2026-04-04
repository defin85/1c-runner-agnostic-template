---
name: web-stop
description: Импортированный compatibility skill из cc-1c-skills. Остановка Apache HTTP Server. Используй когда пользователь просит остановить веб-сервер, Apache, прекратить веб-публикацию
argument-hint: [args...]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /web-stop

Repo script: `./scripts/skills/run-imported-skill.sh web-stop`

## Use When

- Остановка Apache HTTP Server. Используй когда пользователь просит остановить веб-сервер, Apache, прекратить веб-публикацию
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
