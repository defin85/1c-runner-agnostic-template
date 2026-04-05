---
name: web-publish
description: "Импортированный compatibility skill из cc-1c-skills. Prefer native 1c-publish-http. Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере"
argument-hint: "[database]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /web-publish

Repo script: `./scripts/skills/run-imported-skill.sh web-publish`

## Use When

- Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh web-publish --help
./scripts/skills/run-imported-skill.sh web-publish ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/web-publish/SKILL.md`
- Runtime kind: `native-alias`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Для native runner-agnostic workflow предпочитайте: `1c-publish-http`.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
