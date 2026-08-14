---
name: cfe-validate
description: "Импортированный compatibility skill из cc-1c-skills. Валидация расширения конфигурации 1С (CFE). Используй после создания или модификации расширения для проверки корректности"
argument-hint: "<ExtensionPath> [-Detailed] [-MaxErrors 30]"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cfe-validate

Repo script: `./scripts/skills/run-imported-skill.sh cfe-validate`
Windows launcher: `./scripts/skills/run-imported-skill.ps1 cfe-validate`

## Use When

- Валидация расширения конфигурации 1С (CFE). Используй после создания или модификации расширения для проверки корректности
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

## Usage

```bash
./scripts/skills/run-imported-skill.sh cfe-validate --help
./scripts/skills/run-imported-skill.sh cfe-validate ...
```

```powershell
./scripts/skills/run-imported-skill.ps1 cfe-validate --help
./scripts/skills/run-imported-skill.ps1 cfe-validate ...
```

## Adaptation

- Vendored upstream source: `automation/vendor/cc-1c-skills/skills/cfe-validate/SKILL.md`
- Runtime kind: `python`
- Readiness target: `make imported-skills-readiness`
- Direct readiness command: `./scripts/skills/run-imported-skill.sh --readiness`
- Windows readiness command: `./scripts/skills/run-imported-skill.ps1 --readiness`
- Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.

## Rules

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
