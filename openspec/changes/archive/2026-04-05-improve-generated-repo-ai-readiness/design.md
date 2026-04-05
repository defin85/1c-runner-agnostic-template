## Context

Текущий шаблон уже решает несколько сильных задач:

- generated repo получает root router и canonical generated-project onboarding path
- есть checked-in runtime support truth и safe-local baseline
- есть project-scoped skills, включая imported compatibility pack из `cc-1c-skills`
- есть generated-derived inventory и summary-first context

Но audit на реальном generated repo показал системный gap именно на уровне template-managed AI envelope:

1. `project-map.md`, `architecture-map.md` и `runtime-quickstart.md` seed-ятся слишком общими draft-ами и почти не сокращают first-pass discovery без ручного enrichment.
2. Imported skills уже видны агенту, но python/node-backed variants могут падать на missing local deps вроде `lxml` или `playwright`.
3. Full `.agents/skills/README.md` полезен как каталог, но не как компактный first-hour recommendation layer для конкретной формы generated repo.

Если generated repo должен быть максимально AI-ready сразу после bootstrap/update, шаблон должен поставлять не просто docs + scripts, а self-checkable onboarding envelope, который:

- показывает агенту, что runnable прямо сейчас;
- подсказывает, какой subset skills вероятнее всего нужен именно в этой codebase;
- закладывает repo-derived draft context в project-owned файлы;
- механически валит misleading surface до того, как repository будет считаться agent-ready.

## Goals

- Снизить первый onboarding pass новой LLM-сессии в generated repo до одного read-only маршрута и 1-2 follow-up doc hops
- Сделать imported executable skills dependency-aware и fail-closed
- Добавить компактный project-aware recommendation layer поверх полного skill catalog
- Seed-ить generated repo project-owned context файлами, которые уже содержат полезные repo-derived факты
- Проверять эти contracts механически на уровне template verification

## Non-Goals

- Гарантировать, что любой generated repo полностью описан без project-owned enrichment
- Автоматически устанавливать все локальные зависимости imported pack без участия команды/оператора
- Превращать полный skill catalog в жёстко фиксированный wizard или скрывать full surface от агента
- Дублировать domain truth generated repo в template source docs

## Decisions

### Decision: выделить template-managed AI-readiness envelope

Generated repo должен получать единый AI-readiness envelope из трёх слоёв:

1. concise read-only onboarding entrypoint;
2. repo-derived project-owned context drafts;
3. generated-derived recommendations и readiness checks.

Это позволяет не смешивать project-owned truth, template-managed rules и generated-derived hints в один документ.

### Decision: `make codex-onboard` остаётся первой read-only точкой входа

Новый AI-readiness status должен приходить через уже существующий repo-owned entrypoint `make codex-onboard`, а не через новый ad hoc command.

Onboarding output должен дополняться:

- status-подсказкой по imported skill readiness;
- указателем на canonical bootstrap/runbook для executable imported skills;
- ссылкой на compact recommended-skill surface для конкретного generated repo.

### Decision: imported executable skills получают canonical readiness contract

Repo-owned dispatcher для imported skills должен:

- уметь проверять обязательные local dependencies для representative python/node skills;
- при отсутствии зависимостей падать fail-closed с actionable guidance;
- не показывать raw vendored stack traces как primary UX.

Шаблон может ввести canonical bootstrap/check path для imported skills, но публичный contract должен оставаться repo-owned и updateable.

### Decision: full skill catalog и compact recommendation layer разделяются

`.agents/skills/README.md` остаётся полным catalog/mapping surface.
Для first-hour routing шаблон должен генерировать отдельный generated-derived artifact с project-aware recommendations, основанными на repo shape и metadata inventory.

Примеры routing logic:

- если есть `src/cfe` и extension artifacts, рекомендовать `cfe-*`
- если repo содержит forms-heavy footprint, рекомендовать `form-info/edit/validate`
- если видны reports/SKD signals, рекомендовать `skd-*`
- при overlap intent сначала рекомендовать native `1c-*` skills

### Decision: project-owned context seeds должны быть repo-derived draft-ами

Bootstrap/update path должен seed-ить `project-map.md`, `architecture-map.md` и `runtime-quickstart.md` не только Copier answers, но и немедленно доступными repo-derived фактами:

- identity configuration при наличии `Configuration.xml`
- high-signal source roots
- representative first-pass paths
- explicit first-hour routers

При этом файлы остаются project-owned после bootstrap и не превращаются в template-managed manual.

### Decision: readiness contracts входят в baseline verification

`make agent-verify` и related fixture smoke должны проверять не только наличие onboarding/docs surfaces, но и representative imported-skill readiness contract.

Это не означает запуск всех 67 imported skills.
Достаточно representative coverage:

- хотя бы один reference-only imported skill
- хотя бы один python-backed imported skill
- хотя бы один node-backed imported skill

## Risks / Trade-offs

- Более насыщенный bootstrap может сделать seed-once файлы длиннее
  - Mitigation: держать их на уровне first-pass draft и оставлять deep detail в generated-derived layers

- Dependency-aware checks могут сделать baseline строже
  - Mitigation: проверять readiness contract и actionable failure path, а не требовать полноценный heavy local setup по умолчанию

- Project-aware recommendations могут стать noisy или generic
  - Mitigation: генерировать только компактный top subset и держать full catalog отдельно

- Есть риск drift между shell bootstrap и Python fallback bootstrap
  - Mitigation: зафиксировать один canonical generation contract и покрыть его fixture smoke

## Verification Strategy

- `openspec validate improve-generated-repo-ai-readiness --strict --no-interactive`
- `python -m unittest tests.python.test_cross_platform`
- `bash tests/smoke/agent-docs-contract.sh`
- `bash tests/smoke/imported-skills-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `make agent-verify`
