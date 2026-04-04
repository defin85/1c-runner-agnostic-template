---
name: form-patterns
description: Импортированный compatibility skill из cc-1c-skills. Справочник паттернов компоновки управляемых форм 1С. Используй как справочник при проектировании форм — архетипы, конвенции, продвинутые приёмы
argument-hint: (no arguments)
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /form-patterns

Repo script: `./scripts/skills/run-imported-skill.sh form-patterns`

## Use When

- Справочник паттернов компоновки управляемых форм 1С. Используй как справочник при проектировании форм — архетипы, конвенции, продвинутые приёмы
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-patterns --help
./scripts/skills/run-imported-skill.sh form-patterns ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-patterns/SKILL.md`
- Runtime kind: `reference`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
