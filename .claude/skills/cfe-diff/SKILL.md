---
name: cfe-diff
description: "Импортированный compatibility skill из cc-1c-skills. Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объекты, перехватчики, проверка переноса. Используй когда нужно понять что содержит расширение или проверить перенесены ли вставки в конфигурацию"
argument-hint: "-ExtensionPath <path> -ConfigPath <path> [-Mode A|B]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cfe-diff

Repo script: `./scripts/skills/run-imported-skill.sh cfe-diff`

## Use When

- Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объекты, перехватчики, проверка переноса. Используй когда нужно понять что содержит расширение или проверить перенесены ли вставки в конфигурацию
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-diff --help
./scripts/skills/run-imported-skill.sh cfe-diff ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-diff/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
