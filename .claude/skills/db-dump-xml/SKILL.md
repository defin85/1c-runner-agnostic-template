---
name: db-dump-xml
description: "Импортированный compatibility skill из cc-1c-skills. Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles"
argument-hint: "[database] [outputDir]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /db-dump-xml

Repo script: `./scripts/skills/run-imported-skill.sh db-dump-xml`

## Use When

- Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh db-dump-xml --help
./scripts/skills/run-imported-skill.sh db-dump-xml ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/db-dump-xml/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
