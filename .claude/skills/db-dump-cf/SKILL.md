---
name: db-dump-cf
description: "Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит…"
metadata:
  short-description: "Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: db-dump-cf

Repo script: `./scripts/skills/run-imported-skill.sh db-dump-cf`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 db-dump-cf`

## Use When

- Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит выгрузить конфигурацию в CF, сохранить конфигурацию, сделать бэкап CF
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-dump-cf --help
./scripts/skills/run-imported-skill.sh db-dump-cf ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 db-dump-cf --help
./scripts/skills/run-imported-skill.ps1 db-dump-cf ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-dump-cf/SKILL.md`
- Runtime kind: `profile-ibcmd`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Dispatcher выполняет операцию через ibcmd по runtime profile (`-Profile`, по умолчанию `ONEC_PROFILE` или `env/local.json`); vendored helper и Designer не запускаются.
- Параметры: `[-Profile <json>] [-RunRoot <dir>] -OutputFile <cf/cfe> [-Extension <name>]`. Точный контракт: `./scripts/skills/run-imported-skill.sh db-dump-cf --help`.

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
