---
name: epf-dump
description: "Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй ко…"
metadata:
  short-description: "Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй ко…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: epf-dump

Repo script: `./scripts/skills/run-imported-skill.sh epf-dump`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 epf-dump`

## Use When

- Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать обработку, получить исходники из EPF/ERF файла
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-dump --help
./scripts/skills/run-imported-skill.sh epf-dump ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 epf-dump --help
./scripts/skills/run-imported-skill.ps1 epf-dump ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-dump/SKILL.md`
- Runtime kind: `profile-ibcmd`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Dispatcher выполняет операцию через ibcmd по runtime profile (`-Profile`, по умолчанию `ONEC_PROFILE` или `env/local.json`); vendored helper и Designer не запускаются.
- Параметры: `[-Profile <json>] [-RunRoot <dir>] -InputFile <artifact> -OutputDir <dir>`. Точный контракт: `./scripts/skills/run-imported-skill.sh epf-dump --help`.
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
