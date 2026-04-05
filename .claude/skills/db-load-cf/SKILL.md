---
name: db-load-cf
description: "Импортированный compatibility skill из cc-1c-skills. Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF"
argument-hint: "<input.cf> [database]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-load-cf

Repo script: `./scripts/skills/run-imported-skill.sh db-load-cf`

## Use When

- Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-load-cf --help
./scripts/skills/run-imported-skill.sh db-load-cf ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-load-cf/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
