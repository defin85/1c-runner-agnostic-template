---
name: web-unpublish
description: Импортированный compatibility skill из cc-1c-skills. Удаление веб-публикации 1С из Apache. Используй когда пользователь просит убрать публикацию, удалить веб-доступ к базе
argument-hint: <appname | --all>
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /web-unpublish

Repo script: `./scripts/skills/run-imported-skill.sh web-unpublish`

## Use When

- Удаление веб-публикации 1С из Apache. Используй когда пользователь просит убрать публикацию, удалить веб-доступ к базе
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
