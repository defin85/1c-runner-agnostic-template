---
name: form-patterns
description: "Импортированный compatibility skill из `cc-1c-skills`: Справочник паттернов компоновки управляемых форм 1С. Используй как справочник при проектировании форм — архетипы, конвенции, продвинутые приёмы"
metadata:
  short-description: "Справочник паттернов компоновки управляемых форм 1С. Используй как спра…"
---

<!-- GENERATED: sync-imported-skills -->

# Agent Skill: form-patterns

Repo script: `./scripts/skills/run-imported-skill.sh form-patterns`

## Use When

- Справочник паттернов компоновки управляемых форм 1С. Используй как справочник при проектировании форм — архетипы, конвенции, продвинутые приёмы
- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.

## Usage

```bash
./scripts/skills/run-imported-skill.sh form-patterns --help
./scripts/skills/run-imported-skill.sh form-patterns ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/form-patterns/SKILL.md`
- Runtime kind: `reference`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.

## Rules

- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.
- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
- Не переносите upstream PowerShell snippets в новый automation contract шаблона.
