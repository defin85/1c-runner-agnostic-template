# Example Execution Plan

## Goal

Свести generated onboarding к одному маршруту и не потерять project-owned truth.

## Scope And Non-Goals

- Scope:
  - обновить generated onboarding router;
  - синхронизировать curated truth и checks;
  - закрыть smoke/regression coverage.
- Non-goals:
  - не менять прикладную бизнес-логику generated проекта;
  - не вводить новый runtime contour без явного контракта.

## Dependencies And Invariants

- OpenSpec change уже approved.
- Template-managed слой не должен silently перезаписывать project-owned truth.
- Safe-local verify остаётся runnable без licensed 1C binaries.

## Execution Matrix

| Requirement / Task | Code / Docs | Verification | Status |
| --- | --- | --- | --- |
| Обновить generated router | `docs/agent/generated-project-index.md` | `make agent-verify` | done |
| Обновить project-owned digests | `automation/context/**`, `docs/agent/**` | fixture smoke | in_progress |
| Закрыть drift checks | `scripts/qa/check-agent-docs.sh` | smoke + `make agent-verify` | todo |

## Progress

- Canonical router уже определён.
- Runtime matrix уже существует.
- Осталось связать digests и freshness checks.

## Chronological Steps

1. Зафиксировать source of truth для onboarding и runtime.
2. Обновить seeded docs и local routers.
3. Поднять checks и smoke на новый contract.
4. Прогнать финальный verify set.

## Surprises & Discoveries

- Самый опасный drift обычно возникает не в raw inventory, а в коротких curated docs.

## Decision Log

- Runtime quick answers держим в отдельном коротком digest, а не в общем `env/README.md`.
- Project-specific smoke остаётся extension slot, а не частью template baseline по умолчанию.

## Verification State

- `make agent-verify` должен пройти.
- `tests/smoke/agent-docs-contract.sh` должен поймать curated-truth drift.

## Outcomes & Retrospective

- После landing новый агент должен понимать onboarding path за один read-only экран.
