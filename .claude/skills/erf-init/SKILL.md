---
name: erf-init
description: "Импортированный compatibility skill из cc-1c-skills. Создать пустой внешний отчёт 1С (scaffold XML-исходников)"
argument-hint: "<Name> [Synonym] [--with-skd]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /erf-init

Repo script: `./scripts/skills/run-imported-skill.sh erf-init`

## Use When

- Создать пустой внешний отчёт 1С (scaffold XML-исходников)
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-init --help
./scripts/skills/run-imported-skill.sh erf-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-init/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
