---
name: 1c-run-bdd
description: Используйте, когда нужно прогнать BDD или acceptance contour через канонический test entrypoint проекта.
metadata:
  short-description: BDD contour.
---

# Agent Skill: 1c-run-bdd

Repo script: `./scripts/test/run-bdd.sh`
Windows launcher: `./scripts/test/run-bdd.ps1`

## Use When

- Нужно прогнать acceptance или BDD contour.
- Нужен единый adapter-aware запуск с machine-readable артефактами.

## Usage

```bash
./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/run-bdd
./scripts/test/run-bdd.sh --profile env/ci.json --run-root /tmp/run-bdd --dry-run
```

Тёплый контур Vanessa Automation запускается отдельными repo-owned скриптами:

```bash
./scripts/test/run-bdd-warm-service.sh up --profile env/local.json --run-root /tmp/bdd-warm-service-run
ONEC_PROFILE_PATH=env/local.json ONEC_TARGET_ID=<target-id> ONEC_BDD_FEATURES='features/vanessa/example.feature' \
  ./scripts/test/run-bdd-warm-run.sh
./scripts/test/run-bdd-warm-service.sh down --profile env/local.json --run-root /tmp/bdd-warm-service-run
```

## Rules

- Skill описывает intent и entrypoint, но не дублирует test runtime logic.
- `run-bdd.sh` принимает `--profile`, `--run-root` и `--dry-run`; флага `--target` у него нет.
- Профиль `schemaVersion: 3` не принимает `capabilities.bdd.command`. Пока у BDD нет структурированного backend, задавайте `capabilities.bdd.unsupportedReason`: `run-bdd.sh` завершится с кодом 64 и запишет в `summary.json` `execution.executor=builtin-unsupported`, а `doctor` покажет контур как `unsupported`.
- Для тёплого контура набор сценариев задаётся через `ONEC_BDD_MANIFEST`, `ONEC_BDD_FEATURES`, `capabilities.bdd.manifestPath` или `capabilities.bdd.featurePaths`; `run-bdd-warm-run.sh` требует `ONEC_PROFILE_PATH` и `ONEC_TARGET_ID`.
- Для серии BDD-задач используйте job `vanessa-bdd` из [кампании тестирования](../../../docs/testing/testing-campaign.md).
- Основной результат смотрите в `summary.json`.
