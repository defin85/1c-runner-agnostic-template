---
name: db-load-git
description: Импортированный compatibility skill из cc-1c-skills. Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита
argument-hint: [database] [source]
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-load-git

Repo script: `./scripts/skills/run-imported-skill.sh db-load-git`

## Use When

- Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-load-git --help
./scripts/skills/run-imported-skill.sh db-load-git ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-load-git/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.
- Для native runner-agnostic workflow предпочитайте: `1c-load-diff-src`, `1c-load-task-src`.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
