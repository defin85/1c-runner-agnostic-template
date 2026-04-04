---
name: img-grid
description: Импортированный compatibility skill из cc-1c-skills. Наложить пронумерованную сетку на изображение для определения пропорций колонок
argument-hint: <ImagePath> [-c COLS]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /img-grid

Repo script: `./scripts/skills/run-imported-skill.sh img-grid`

## Use When

- Наложить пронумерованную сетку на изображение для определения пропорций колонок
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh img-grid --help
./scripts/skills/run-imported-skill.sh img-grid ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/img-grid/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
