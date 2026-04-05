---
name: db-create
description: "Импортированный compatibility skill из cc-1c-skills. Prefer native 1c-create-ib. Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу"
argument-hint: "<path|name>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-create

Repo script: `./scripts/skills/run-imported-skill.sh db-create`

## Use When

- Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-create --help
./scripts/skills/run-imported-skill.sh db-create ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-create/SKILL.md`
- Runtime kind: `native-alias`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Для native runner-agnostic workflow предпочитайте: `1c-create-ib`.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
