---
name: 1c-doctor
description: >
  Этот скилл MUST быть вызван, когда пользователь просит диагностировать
  готовность runtime-профиля, adapter config и базовых зависимостей проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-doctor

Repo script: `./scripts/diag/doctor.sh`

## Use When

- Нужно быстро проверить readiness runtime environment.
- Нужно понять, каких tool/env dependency не хватает до запуска 1С-контуров.

## Usage

```bash
./scripts/diag/doctor.sh --profile env/local.json
./scripts/diag/doctor.sh --profile env/ci.json --run-root /tmp/doctor-run
./scripts/diag/doctor.sh --profile env/local.json --dry-run
```

## Rules

- Этот skill не должен подменять собой actual runtime capabilities; он только проверяет readiness.
- Вердикт и список missing dependency брать из `summary.json`.
