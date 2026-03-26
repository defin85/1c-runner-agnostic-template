## Контекст

Шаблон уже различает:

- `OpenSpec` для change contract;
- `bd` для live execution tracking;
- `docs/exec-plans/` для long-running progress и handoff.

Этого недостаточно для задач, у которых кроме progress есть ещё bulky supporting materials: summaries писем и вложений, extracted task notes, decisions, evidence links, temporary integration notes и другие артефакты, которые не являются ни спецификацией, ни кодом, ни коротким execution plan.

## Goals

- Дать generated repos canonical project-owned workspace для task-local supporting artifacts.
- Явно развести роли `OpenSpec`, `bd`, `docs/exec-plans/` и `docs/work-items/`.
- Избежать ad-hoc папок вроде `tasks/roadmap` и смешивания process artifacts с кодом в `src/`.
- Сделать новый workspace discoverable из onboarding и mechanically проверяемым.

## Non-Goals

- Не превращать `docs/work-items/` в новый issue tracker или замену `bd`.
- Не дублировать в `docs/work-items/` progress, который уже должен жить в `docs/exec-plans/`.
- Не навязывать projects обязательное заполнение work-item folders для каждой маленькой задачи.

## Решения

### 1. Использовать `docs/work-items/`, а не `tasks/roadmap`

`tasks/roadmap` смешивает разные смыслы:

- `tasks` звучит как tracker;
- `roadmap` звучит как portfolio planning.

Для generated repos лучше использовать `docs/work-items/` как project-owned documentation workspace, потому что это явно companion к `docs/exec-plans/` и не притворяется tracker-ом.

### 2. Развести роли `exec-plans` и `work-items`

- `docs/exec-plans/active/<name>.md` остаётся одним self-contained living plan для progress, handoff и session restart.
- `docs/work-items/<task-id>/` становится местом для bulky supporting artifacts:
  - extracted notes;
  - summaries raw attachments;
  - integration notes;
  - task-local evidence;
  - related links и inputs.

### 3. Seed-ить минимальный scaffold

Шаблон seed-ит:

- `docs/work-items/README.md` — правила роли и структуры;
- `docs/work-items/TEMPLATE.md` — copy-ready starter для `docs/work-items/<task-id>/index.md`.

Этого достаточно, чтобы generated repo не изобретал свою структуру с нуля, но при этом не тащил лишнюю template-managed глубину.

### 4. Сделать routing явным, а не implicit

Generated onboarding и Codex workflow docs должны прямо объяснять:

- когда оставаться в `OpenSpec`;
- когда идти в `bd`;
- когда создавать `docs/exec-plans/active/...`;
- когда заводить `docs/work-items/<task-id>/`.

## Риски / Trade-offs

- Появится ещё один agent-facing слой, который можно запустить в drift.
  - Смягчение: держать его минимальным и покрыть static/fixture checks.
- Команда может начать дублировать progress и в `exec-plan`, и в `work-items`.
  - Смягчение: README/TEMPLATE должны жёстко разделять роли.
- Некоторые проекты всё равно захотят `roadmap` для portfolio planning.
  - Это допустимо, но отдельным project-owned слоем, не как замена `docs/work-items/`.

## Open Questions

- Нужен ли в следующем change example work-item folder, или на первом шаге достаточно `README + TEMPLATE`?
