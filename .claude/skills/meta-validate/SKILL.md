---
name: meta-validate
description: Импортированный compatibility skill из cc-1c-skills. Валидация объекта метаданных 1С. Используй после создания или модификации объекта конфигурации для проверки корректности
argument-hint: <ObjectPath> [-Detailed] [-MaxErrors 30] — pipe-separated paths for batch
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /meta-validate

Repo script: `./scripts/skills/run-imported-skill.sh meta-validate`

## Use When

- Валидация объекта метаданных 1С. Используй после создания или модификации объекта конфигурации для проверки корректности
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh meta-validate --help
./scripts/skills/run-imported-skill.sh meta-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/meta-validate/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
