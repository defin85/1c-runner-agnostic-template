---
name: db-load-git
description: Импортированный compatibility skill из `cc-1c-skills`: Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита
metadata:
  short-description: Загрузка изменений из Git в базу 1С. Используй когда пользователь проси…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-load-git

Repo script: `./scripts/skills/run-imported-skill.sh db-load-git`

## Use When

- Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

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

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
