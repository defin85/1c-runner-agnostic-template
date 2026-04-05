---
name: mxl-compile
description: "Импортированный compatibility skill из cc-1c-skills. Компиляция табличного документа (MXL) из JSON-определения. Используй когда нужно создать макет печатной формы"
argument-hint: "<JsonPath> <OutputPath>"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /mxl-compile

Repo script: `./scripts/skills/run-imported-skill.sh mxl-compile`

## Use When

- Компиляция табличного документа (MXL) из JSON-определения. Используй когда нужно создать макет печатной формы
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh mxl-compile --help
./scripts/skills/run-imported-skill.sh mxl-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/mxl-compile/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
