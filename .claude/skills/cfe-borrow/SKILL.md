---
name: cfe-borrow
description: Импортированный compatibility skill из cc-1c-skills. Заимствование объектов из конфигурации 1С в расширение (CFE). Используй когда нужно перехватить метод, изменить форму или добавить реквизит к существующему объекту конфигурации
argument-hint: -ExtensionPath <path> -ConfigPath <path> -Object "Catalog.Контрагенты.Form.ФормаЭлемента" -BorrowMainAttribute
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cfe-borrow

Repo script: `./scripts/skills/run-imported-skill.sh cfe-borrow`

## Use When

- Заимствование объектов из конфигурации 1С в расширение (CFE). Используй когда нужно перехватить метод, изменить форму или добавить реквизит к существующему объекту конфигурации
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-borrow --help
./scripts/skills/run-imported-skill.sh cfe-borrow ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-borrow/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
