---
name: db-run
description: "Импортированный compatibility skill из cc-1c-skills. Запуск 1С:Предприятие. Используй когда пользователь просит запустить 1С, открыть базу, запустить предприятие"
argument-hint: "[database]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-run

Repo script: `./scripts/skills/run-imported-skill.sh db-run`

## Use When

- Запуск 1С:Предприятие. Используй когда пользователь просит запустить 1С, открыть базу, запустить предприятие
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-run --help
./scripts/skills/run-imported-skill.sh db-run ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-run/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
