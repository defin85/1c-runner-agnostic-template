---
name: cfe-patch-method
description: "Импортированный compatibility skill из cc-1c-skills. Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального"
argument-hint: "-ExtensionPath <path> -ModulePath \"Catalog.X.ObjectModule\" -MethodName \"ПриЗаписи\" -InterceptorType Before"
allowed-tools:
  - Bash
  - Read
  - Glob
---

<!-- GENERATED: sync-imported-skills -->

# /cfe-patch-method

Repo script: `./scripts/skills/run-imported-skill.sh cfe-patch-method`

## Use When

- Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального
- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.

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

- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.
- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.
- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.
