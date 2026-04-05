---
name: mxl-info
description: "Импортированный compatibility skill из cc-1c-skills. Анализ структуры макета табличного документа (MXL) — области, параметры, наборы колонок. Используй при разработке печати — получить области и заполняемые параметры макета"
argument-hint: "<TemplatePath> или <ProcessorName> <TemplateName>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /mxl-info

Repo script: `./scripts/skills/run-imported-skill.sh mxl-info`

## Use When

- Анализ структуры макета табличного документа (MXL) — области, параметры, наборы колонок. Используй при разработке печати — получить области и заполняемые параметры макета
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh mxl-info --help
./scripts/skills/run-imported-skill.sh mxl-info ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/mxl-info/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
