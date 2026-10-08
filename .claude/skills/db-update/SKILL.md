---
name: db-update
description: "Prefer native 1c-update-db. Обновление конфигурации базы данных 1С. Исп…"
metadata:
  short-description: "Prefer native 1c-update-db. Обновление конфигурации базы данных 1С. Исп…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-update

Repo script: `./scripts/skills/run-imported-skill.sh db-update`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 db-update`

## Use When

- Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-update --help
./scripts/skills/run-imported-skill.sh db-update ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 db-update --help
./scripts/skills/run-imported-skill.ps1 db-update ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-update/SKILL.md`
- Runtime kind: `native-alias`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Параметры: `[--profile <json>] [--run-root <dir>]`. Точный контракт: `./scripts/skills/run-imported-skill.sh db-update --help`.
- Запуск требует driver `ibcmd` для capability `update-db` в runtime profile; перехода на Designer нет.
- Для native runner-agnostic workflow предпочитайте: `1c-update-db`.

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
