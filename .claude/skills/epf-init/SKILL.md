---
name: epf-init
description: "Импортированный compatibility skill из cc-1c-skills. Создать пустую внешнюю обработку 1С (scaffold XML-исходников)"
argument-hint: "<Name> [Synonym]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /epf-init

Repo script: `./scripts/skills/run-imported-skill.sh epf-init`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 epf-init`

## Use When

- Создать пустую внешнюю обработку 1С (scaffold XML-исходников)
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh epf-init --help
./scripts/skills/run-imported-skill.sh epf-init ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 epf-init --help
./scripts/skills/run-imported-skill.ps1 epf-init ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/epf-init/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
