## 1. Spec And Ownership Contract

- [x] 1.1 Зафиксировать capability `generated-project-agent-guidance` с generated-project-first onboarding, ownership classes, context/export contract и verification matrix.
- [x] 1.2 Расширить `template-ci-contours` требованиями к ownership/freshness/maintenance checks для agent-facing generated-project surface.

## 2. Generated-Project Onboarding Surface

- [x] 2.1 Переработать generated-project root onboarding так, чтобы `README.md` и `AGENTS.md` не позиционировали generated repo как template source repo.
- [x] 2.2 Вынести template maintenance guidance в отдельный template-managed doc и убрать его из primary feature/onboarding path generated project.
- [x] 2.3 Явно задокументировать ownership classes и какие артефакты относятся к `template-managed`, `seed-once / project-owned`, `generated-derived`, `local-private`.

## 3. Project Context And Export Tooling

- [x] 3.1 Заменить placeholder-oriented generated-project context templates на concrete starter artifacts, основанные на Copier answers и repo layout.
- [x] 3.2 Разделить curated project context и generated-derived inventory по разным путям/именам файлов.
- [x] 3.3 Обновить `scripts/llm/export-context.sh` или эквивалентный repo-owned export path так, чтобы он поддерживал `help/check/preview/write` contract без write-by-default.

## 4. Verification And Delivery Checks

- [x] 4.1 Добавить generated-project verification matrix с явным делением на `safe local`, `profile-required`, `provisioned/self-hosted 1C`.
- [x] 4.2 Обновить static/fixture checks для ownership drift, placeholder lint, freshness generated artifacts и advertised template-maintenance workflow.
- [x] 4.3 Расширить `tests/smoke/copier-update-ready.sh` и связанные checks так, чтобы canonical maintenance path либо проходил, либо не рекламировался как guaranteed-safe.

## 5. Validation

- [x] 5.1 Прогнать `openspec validate add-generated-project-agent-ownership-model --strict --no-interactive`.
- [x] 5.2 Прогнать минимальный relevant verification set для proposal-aligned docs/contracts после имплементации: `make agent-verify`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`.
