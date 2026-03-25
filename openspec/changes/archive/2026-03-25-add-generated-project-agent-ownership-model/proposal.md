# Change: ввести ownership model для agent-facing surface generated projects

## Why

Шаблон уже хорошо поставляет reusable runtime/tooling surface для generated projects, но граница владения agent-facing артефактами остаётся размытой.

Сейчас generated repository получает:

- template-managed onboarding и maintenance guidance, которые частично выглядят как truth про сам проект;
- placeholder-oriented context templates без явного ownership contract;
- repo-owned utility `scripts/llm/export-context.sh`, который ориентирован на source repo и по умолчанию пишет файлы;
- `copier` maintenance path, который должен быть update-safe, но не закреплён как agent-facing ownership contract.

Из-за этого новый агент и команда generated project не понимают:

- какие файлы являются shared template contract и могут обновляться вместе с шаблоном;
- какие файлы должны стать project-owned truth и не должны перетираться `copier update`;
- какие артефакты являются generated-derived inventory и должны регенерироваться через явный script path;
- какие локальные Codex/MCP/runtime настройки вообще не являются частью checked-in template contract.

Нужен явный ownership model для generated-project agent surface, чтобы template update оставался безопасным, а project-specific truth не конфликтовал с reusable template assets.

## What Changes

- добавить новую capability `generated-project-agent-guidance`, которая зафиксирует:
  - generated-project-first root onboarding surface;
  - update-safe ownership classes для agent-facing артефактов;
  - project-owned curated context отдельно от generated-derived inventories;
  - verification matrix для generated projects;
  - side-effect-transparent context export contract;
- расширить `template-ci-contours`, чтобы static/fixture contour проверял ownership boundaries, placeholder drift, freshness generated artifacts и честность advertised template-maintenance workflow;
- зафиксировать, что template layer владеет только reusable operational contract, а project truth в generated repository принадлежит самому проекту.

## Out Of Scope

- Полная автоматическая доменная картография произвольной 1С-конфигурации.
- Machine-specific MCP defaults, локальные секреты и host-specific Codex overrides.
- Изменение runtime adapter behavior, не связанное напрямую с agent-facing ownership model.
- Дублирование existing shared skills в vendor-specific packaging сверх уже существующих `.agents/skills/` и `.claude/skills/`.

## Impact

- Affected specs:
  - `generated-project-agent-guidance` (new)
  - `template-ci-contours`
- Affected code:
  - `README.md`
  - `scripts/bootstrap/copier-post-copy.sh`
  - `scripts/bootstrap/copier-post-update.sh`
  - `scripts/bootstrap/agents-overlay.sh`
  - `docs/agent/*`
  - `docs/template-maintenance.md` or equivalent generated-project maintenance doc
  - `automation/context/templates/*`
  - `scripts/llm/export-context.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `tests/smoke/copier-update-ready.sh`
  - `Makefile`
  - `.github/workflows/ci.yml`
