---
name: erf-dump
description: "Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользоват…"
metadata:
  short-description: "Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользоват…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: erf-dump

Repo script: `./scripts/skills/run-imported-skill.sh erf-dump`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 erf-dump`

## Use When

- Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-dump --help
./scripts/skills/run-imported-skill.sh erf-dump ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 erf-dump --help
./scripts/skills/run-imported-skill.ps1 erf-dump ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-dump/SKILL.md`
- Runtime kind: `profile-ibcmd`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Dispatcher выполняет операцию через ibcmd по runtime profile (`-Profile`, по умолчанию `ONEC_PROFILE` или `env/local.json`); vendored helper и Designer не запускаются.
- Параметры: `[-Profile <json>] [-RunRoot <dir>] -InputFile <artifact> -OutputDir <dir>`. Точный контракт: `./scripts/skills/run-imported-skill.sh erf-dump --help`.
- Сборка и выгрузка берут контекст метаданных из ИБ профиля; временная ИБ не создаётся, параметры `-V8Path` и `-InfoBase*` не поддерживаются.

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
