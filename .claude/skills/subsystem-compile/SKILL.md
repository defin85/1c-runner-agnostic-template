---
name: subsystem-compile
description: "Импортированный compatibility skill из cc-1c-skills. Создать подсистему 1С — XML-исходники из JSON-определения. Используй когда пользователь просит добавить подсистему (раздел) в конфигурацию"
argument-hint: "[-DefinitionFile <json> | -Value <json-string>] -OutputDir <ConfigDir> [-Parent <path>]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /subsystem-compile

Repo script: `./scripts/skills/run-imported-skill.sh subsystem-compile`

## Use When

- Создать подсистему 1С — XML-исходники из JSON-определения. Используй когда пользователь просит добавить подсистему (раздел) в конфигурацию
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh subsystem-compile --help
./scripts/skills/run-imported-skill.sh subsystem-compile ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/subsystem-compile/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
