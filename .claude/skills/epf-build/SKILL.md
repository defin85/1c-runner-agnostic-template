---
name: epf-build
description: "Импортированный compatibility skill из cc-1c-skills. Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать обработку или получить EPF/ERF файл из исходников"
argument-hint: "<ProcessorName>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-build

Repo script: `./scripts/skills/run-imported-skill.sh epf-build`

## Use When

- Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать обработку или получить EPF/ERF файл из исходников
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-build --help
./scripts/skills/run-imported-skill.sh epf-build ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-build/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
