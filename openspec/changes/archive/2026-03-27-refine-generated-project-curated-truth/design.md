## Контекст

Шаблон уже даёт generated repo хороший first-hour router, runtime support matrix и safe-local verify path. Однако новое ревью target repo показало, что после первого шага агенту всё ещё не хватает reusable следующего слоя:

- один canonical Codex workflow surface вместо повторяющихся списков controls;
- один operator-local runbook scaffold вместо ручной навигации между `runtime-quickstart`, `env/README.md` и project-owned runtime docs;
- один generated-derived project-delta artifact, который можно подкладывать под curated project map без knowledge о конкретном домене проекта;
- stricter checks, которые удерживают эти curated truth surfaces в актуальном состоянии.

## Goals

- Уменьшить routing noise в generated root surfaces и собрать Codex-native workflow guidance в один canonical doc.
- Дать generated repos reusable scaffold для operator-local runtime decisions.
- Добавить generic project-delta artifact, который помогает проектам быстрее находить собственные кастомизации поверх типового слоя.
- Сделать новую curated truth mechanically checkable в static и fixture verification.

## Non-Goals

- Не зашивать в шаблон доменные bounded contexts конкретного проекта вроде ROLF.
- Не делать template-managed прикладную архитектурную карту вместо project-owned документов.
- Не превращать generated project в source repo OpenSpec mirror и не навязывать конкретные living specs бизнес-домена.

## Решения

### 1. Один canonical workflow doc

В generated repos появляется `docs/agent/codex-workflows.md` как единственный authoritative doc для:

- session controls (`/plan`, `/compact`, `/review`, `/ps`, `/mcp`);
- long-running flow и `docs/exec-plans/*`;
- review-only flow;
- skills/MCP pointers;
- связи между `OpenSpec`, `bd` и execution plans.

Root `AGENTS.md`, root `README.md`, `generated-project-index.md` и `.codex/README.md` остаются pointer surfaces и перестают дублировать развернутые workflow sections.

### 2. Operator-local runbook как project-owned scaffold

Шаблон seed-ит `docs/agent/operator-local-runbook.md`, который проект наполняет фактами про local-private или operator-owned contours. `runtime-quickstart` и onboarding router должны использовать его как короткий bridge для вопросов вида “могу ли я реально запустить contour локально?”.

### 3. Project-delta hints и generated artifact

Шаблон seed-ит project-owned hint artifact, из которого `export-context` сможет построить generated-derived `automation/context/project-delta-hotspots.generated.md`.

Этот слой должен:

- оставаться generic и не знать домен конкретного проекта заранее;
- опираться на project-owned hints вроде prefixes, representative roots, object families или other stable selectors;
- давать summary-first ссылку на project-specific customization layer рядом с общим `hotspots-summary.generated.md`.

### 4. Freshness checks только на механически проверяемые истины

Static/fixture checks не должны пытаться доказать, что project-owned domain map “достаточно умна”. Вместо этого они должны валидировать:

- что representative paths из curated docs существуют;
- что canonical workflow doc существует и маршрутизируется одинаково из root surfaces;
- что operator-local runbook связан с runtime matrix/quickstart;
- что project-delta hints и generated project-delta artifact не расходятся по declared selectors и advertised paths.

## Риски / Trade-offs

- Новый project-delta artifact увеличит число agent-facing файлов и может сам стать источником drift.
  - Смягчение: generated-derived статус, deterministic refresh path и explicit freshness checks.
- Canonical workflow doc может превратиться во второй большой индекс.
  - Смягчение: держать в нём только Codex-specific mechanics, а не повторять весь onboarding router.
- Operator-local runbook scaffold может остаться пустой формальностью.
  - Смягчение: checks должны валидировать минимальный contract и связность с runtime quickstart, но не требовать project-specific наполнения до появления реальных operator-local contours.

## Open Questions

- Хватит ли project-delta hints как отдельного JSON/Markdown artifact, или проектам удобнее хранить hints как managed block внутри `project-map.md`?
- Нужен ли отдельный `make codex-workflows` helper, или достаточно одного canonical doc и ссылки из `make codex-onboard`?
