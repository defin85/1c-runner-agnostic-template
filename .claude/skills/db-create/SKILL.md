---
name: db-create
description: "Prefer native 1c-create-ib. Создание информационной базы 1С. Используй…"
metadata:
  short-description: "Prefer native 1c-create-ib. Создание информационной базы 1С. Используй…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-create

Repo script: `./scripts/skills/run-imported-skill.sh db-create`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 db-create`

## Use When

- Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-create --help
./scripts/skills/run-imported-skill.sh db-create ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 db-create --help
./scripts/skills/run-imported-skill.ps1 db-create ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-create/SKILL.md`
- Runtime kind: `native-alias`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Параметры: `[--profile <json>] [--run-root <dir>]`. Точный контракт: `./scripts/skills/run-imported-skill.sh db-create --help`.
- Запуск требует driver `ibcmd` для capability `create-ib` в runtime profile; перехода на Designer нет.
- Для native runner-agnostic workflow предпочитайте: `1c-create-ib`.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Параметры определяет `--help` repo-owned dispatcher; vendored upstream `SKILL.md` описывает исходный инструмент, а не текущий контракт.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.

## Наблюдение запуска

Запуск ibcmd или клиента наблюдается общим адаптером: run-root содержит `observation.jsonl`, `summary.json`,
`stdout.log` и `stderr.log`, пароли в них скрыты. Состояние долгого запуска смотрите через
[1c-observe-run](../1c-observe-run/SKILL.md). Остановка при неизменном прогрессе включается
только порогом `ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS` вызывающей обёртки.
