---
name: db-run
description: "Prefer native 1c-run-client. Запуск 1С:Предприятие. Используй когда пол…"
metadata:
  short-description: "Prefer native 1c-run-client. Запуск 1С:Предприятие. Используй когда пол…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-run

Repo script: `./scripts/skills/run-imported-skill.sh db-run`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 db-run`

## Use When

- Запуск 1С:Предприятие. Используй когда пользователь просит запустить 1С, открыть базу, запустить предприятие
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-run --help
./scripts/skills/run-imported-skill.sh db-run ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 db-run --help
./scripts/skills/run-imported-skill.ps1 db-run ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-run/SKILL.md`
- Runtime kind: `native-alias`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.
- Параметры: `[start] [--profile <json>] [--run-root <dir>] | screenshot|status|stop|key|click --run-root <dir>`. Точный контракт: `./scripts/skills/run-imported-skill.sh db-run --help`.
- Вызов проксируется в `./scripts/platform/run-client.sh` (навык `1c-run-client`): подключение и пароль берутся из runtime profile. Прежняя форма с `-V8Path`/`-InfoBase*`/`-Password` отклоняется.
- Для native runner-agnostic workflow предпочитайте: `1c-run-client`.

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
