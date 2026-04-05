---
name: epf-bsp-init
description: "Импортированный compatibility skill из cc-1c-skills. Добавить функцию регистрации БСП (СведенияОВнешнейОбработке) в модуль объекта обработки"
argument-hint: "<ProcessorName> <Вид>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-bsp-init

Repo script: `./scripts/skills/run-imported-skill.sh epf-bsp-init`

## Use When

- Добавить функцию регистрации БСП (СведенияОВнешнейОбработке) в модуль объекта обработки
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-bsp-init --help
./scripts/skills/run-imported-skill.sh epf-bsp-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-bsp-init/SKILL.md`
- Runtime kind: `reference`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
