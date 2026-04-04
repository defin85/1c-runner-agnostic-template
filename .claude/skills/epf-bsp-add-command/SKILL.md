---
name: epf-bsp-add-command
description: Импортированный compatibility skill из cc-1c-skills. Добавить команду в дополнительную обработку БСП
argument-hint: <ProcessorName> <Идентификатор> [ТипКоманды] [Представление]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-bsp-add-command

Repo script: `./scripts/skills/run-imported-skill.sh epf-bsp-add-command`

## Use When

- Добавить команду в дополнительную обработку БСП
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-bsp-add-command --help
./scripts/skills/run-imported-skill.sh epf-bsp-add-command ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-bsp-add-command/SKILL.md`
- Runtime kind: `reference`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
