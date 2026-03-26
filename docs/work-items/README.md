# Work Items

`docs/work-items/` является project-owned workspace для supporting artifacts длинных задач.
Используйте его, когда одного change contract в `OpenSpec` и одного living progress файла в `docs/exec-plans/` уже недостаточно.

## Role Separation

- `OpenSpec` — change contract, requirements, acceptance.
- `bd` — executable tracking и live status.
- `docs/exec-plans/active/<task-id>.md` — living progress, handoff и session restart.
- `docs/work-items/<task-id>/` — extracted notes, attachment summaries, bulky inputs, task-local evidence и supporting materials.

## When To Create A Work-Item Folder

1. У задачи есть дополнительные материалы, которые не должны жить в `src/`.
2. Нужны extracted summaries для raw attachments, писем или operator notes.
3. Нужны task-local evidence links, integration notes или bulky references рядом с exec-plan.

## What Not To Put Here

- не используйте `docs/work-items/` как замену `bd`;
- не дублируйте здесь progress, который уже должен жить в `docs/exec-plans/`;
- не переносите сюда code payload из `src/`.

## Suggested Layout

- `docs/work-items/<task-id>/index.md` — task-local landing page;
- `docs/work-items/<task-id>/notes.md` — extracted notes и summaries;
- `docs/work-items/<task-id>/attachments/` — raw supporting files, если их правда нужно version-control-ить;
- `docs/exec-plans/active/<task-id>.md` — companion living plan с progress и handoff.

## Starter Workflow

1. Если change новый или неоднозначный, начните с `OpenSpec`.
2. После approval переведите execution tracking в `bd`.
3. Скопируйте `docs/exec-plans/TEMPLATE.md` в `docs/exec-plans/active/<task-id>.md`.
4. Если нужны bulky supporting artifacts, скопируйте `docs/work-items/TEMPLATE.md` в `docs/work-items/<task-id>/index.md`.

## Related Truth

- planning guide: [docs/agent/codex-workflows.md](../agent/codex-workflows.md)
- onboarding router: [docs/agent/generated-project-index.md](../agent/generated-project-index.md)
- execution plans contract: [docs/exec-plans/README.md](../exec-plans/README.md)
- work-item starter: [docs/work-items/TEMPLATE.md](TEMPLATE.md)
