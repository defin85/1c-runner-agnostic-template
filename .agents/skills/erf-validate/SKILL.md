---
name: erf-validate
description: Импортированный compatibility skill из `cc-1c-skills`: Валидация внешнего отчёта 1С (ERF). Используй после создания или модификации отчёта для проверки корректности
metadata:
  short-description: Валидация внешнего отчёта 1С (ERF). Используй после создания или модифи…
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: erf-validate

Repo script: `./scripts/skills/run-imported-skill.sh erf-validate`

## Use When

- Валидация внешнего отчёта 1С (ERF). Используй после создания или модификации отчёта для проверки корректности
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-validate --help
./scripts/skills/run-imported-skill.sh erf-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-validate/SKILL.md`
- Runtime kind: `python`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
