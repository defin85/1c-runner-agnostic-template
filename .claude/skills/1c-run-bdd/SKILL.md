---
name: 1c-run-bdd
description: >
  Этот скилл MUST быть вызван, когда пользователь просит запустить BDD /
  acceptance-контур через канонический test entrypoint проекта.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-run-bdd

Repo script: `./scripts/test/run-bdd.sh`

## Use When

- Нужно прогнать acceptance или BDD-контур.
- Нужен единый adapter-aware запуск с machine-readable артефактами.

## Usage

```bash
./scripts/test/run-bdd.sh --profile env/local.json --target <target-id>
./scripts/test/run-bdd.sh --profile env/ci.json --target <target-id> --run-root /tmp/run-bdd
./scripts/test/run-bdd.sh --profile env/local.json --target <target-id> --dry-run
ONEC_BDD_FEATURES='features/vanessa/example.feature' ./scripts/test/run-bdd.sh --profile env/local.json --target <target-id> --run-root /tmp/run-bdd
```

## Rules

- Skill описывает intent и entrypoint, но не дублирует test runtime logic.
- В multi-target репозитории явно передавать `--target`.
- Для warmed BDD runner профиль задает `capabilities.bdd.command = ["./scripts/test/run-bdd-warm-run.sh"]`.
- Набор сценариев для warmed runner задается через `ONEC_BDD_MANIFEST`, `ONEC_BDD_FEATURES`, `capabilities.bdd.manifestPath` или `capabilities.bdd.featurePaths`.
- Основной результат смотреть в `summary.json`.
