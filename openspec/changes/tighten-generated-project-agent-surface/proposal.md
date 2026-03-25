# Change: tighten generated-project agent surface

## Why

После перехода на overlay releases generated repos стали лучше различать `template-managed` и `project-owned` слои, но agent-facing surface всё ещё даёт неоднозначный onboarding и неполный machine context.

Проблемы не в runtime entrypoint-ах, а в legibility:

- shared docs и nested instructions местами ведут нового агента в source-repo-centric path вместо generated-project-first route;
- generated-derived context artifacts не заполняют critical identity fields и протаскивают `local-private` шум;
- QA checks подтверждают форму документов, но слабо валидируют semantic freshness, privacy boundaries и local-only closeout contract.

## What Changes

- Нормализовать generated-project instruction chain в shared template-managed docs и nested `AGENTS.md` так, чтобы generated repo не стартовал с source-repo-centric mental model.
- Сделать generated root guidance более router-like: явные ссылки на verify, review, skills, long-running plans и closeout semantics для local-only repos.
- Добавить Codex-first onboarding/runbook для первых минут работы в generated repo без дублирования source-repo docs.
- Усилить `export-context.sh` для generated repos: вытягивать critical identity из `Configuration.xml`, исключать `local-private` артефакты и выдавать более полезный entrypoint-oriented inventory.
- Расширить semantic checks и fixture smoke для agent-facing docs/context: ловить onboarding conflicts, privacy leaks, empty critical fields и неверный closeout contract.

## Non-Goals

- Наполнять шаблон project-specific truth о конкретной конфигурации generated repo.
- Автоматически писать business-domain architecture map за команду generated проекта.
- Менять runtime capability contract, adapter model или overlay delivery model.

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
- Affected code:
  - `scripts/bootstrap/agents-overlay.sh`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `docs/README.md`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/generated-project-verification.md`
  - `docs/agent/review.md`
  - `.codex/README.md`
  - `docs/exec-plans/README.md`
  - `automation/AGENTS.md`
  - `src/AGENTS.md` and/or `docs/AGENTS.md` if introduced
  - `scripts/llm/export-context.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `tests/smoke/agent-docs-contract.sh`
  - `tests/smoke/bootstrap-agents-overlay.sh`
