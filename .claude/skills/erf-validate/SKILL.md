---
name: erf-validate
description: "Импортированный compatibility skill из cc-1c-skills. Валидация внешнего отчёта 1С (ERF). Используй после создания или модификации отчёта для проверки корректности"
argument-hint: "<ObjectPath> [-Detailed] [-MaxErrors 30]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /erf-validate

Repo script: `./scripts/skills/run-imported-skill.sh erf-validate`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 erf-validate`

## Use When

- Валидация внешнего отчёта 1С (ERF). Используй после создания или модификации отчёта для проверки корректности
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh erf-validate --help
./scripts/skills/run-imported-skill.sh erf-validate ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 erf-validate --help
./scripts/skills/run-imported-skill.ps1 erf-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/erf-validate/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
