---
name: interface-validate
description: "Импортированный compatibility skill из cc-1c-skills. Валидация командного интерфейса 1С. Используй после настройки командного интерфейса подсистемы для проверки корректности"
argument-hint: "<CIPath> [-Detailed] [-MaxErrors 30]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /interface-validate

Repo script: `./scripts/skills/run-imported-skill.sh interface-validate`

## Use When

- Валидация командного интерфейса 1С. Используй после настройки командного интерфейса подсистемы для проверки корректности
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh interface-validate --help
./scripts/skills/run-imported-skill.sh interface-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/interface-validate/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
