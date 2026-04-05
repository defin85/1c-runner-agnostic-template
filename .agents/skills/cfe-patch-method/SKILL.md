---
name: cfe-patch-method
description: "Импортированный compatibility skill из `cc-1c-skills`: Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального"
metadata:
  short-description: "Генерация перехватчика метода в расширении 1С (CFE). Используй когда ну…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: cfe-patch-method

Repo script: `./scripts/skills/run-imported-skill.sh cfe-patch-method`

## Use When

- Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-patch-method --help
./scripts/skills/run-imported-skill.sh cfe-patch-method ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-patch-method/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
