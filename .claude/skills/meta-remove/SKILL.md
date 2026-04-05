---
name: meta-remove
description: "Импортированный compatibility skill из cc-1c-skills. Удалить объект метаданных из конфигурации 1С. Используй когда пользователь просит удалить, убрать объект из конфигурации"
argument-hint: "<ConfigDir> -Object <Type.Name>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /meta-remove

Repo script: `./scripts/skills/run-imported-skill.sh meta-remove`

## Use When

- Удалить объект метаданных из конфигурации 1С. Используй когда пользователь просит удалить, убрать объект из конфигурации
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh meta-remove --help
./scripts/skills/run-imported-skill.sh meta-remove ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/meta-remove/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
