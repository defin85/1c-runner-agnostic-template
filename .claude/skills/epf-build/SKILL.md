---
name: epf-build
description: "Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй ког…"
metadata:
  short-description: "Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй ког…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: epf-build

Repo script: `./scripts/skills/run-imported-skill.sh epf-build`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 epf-build`

## Use When

- Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать обработку или получить EPF/ERF файл из исходников
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-build --help
./scripts/skills/run-imported-skill.sh epf-build ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 epf-build --help
./scripts/skills/run-imported-skill.ps1 epf-build ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-build/SKILL.md`
- Runtime kind: `profile-ibcmd`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Dispatcher выполняет операцию через ibcmd по runtime profile (`-Profile`, по умолчанию `ONEC_PROFILE` или `env/local.json`); vendored helper и Designer не запускаются.
- Параметры: `[-Profile <json>] [-RunRoot <dir>] -SourceFile <xml> -OutputFile <artifact>`. Точный контракт: `./scripts/skills/run-imported-skill.sh epf-build --help`.
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
