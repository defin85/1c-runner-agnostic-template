# Change: Добавить generated-project workspace для long-running work items

## Почему

`OpenSpec` хорошо работает как contract-first слой, а `docs/exec-plans/` уже закрывает living progress и handoff для длинных задач.
Однако generated repo пока не получает отдельный, versioned и agent-friendly workspace для supporting artifacts: extracted notes, summaries вложений, task-local inputs, decisions и other bulky materials, которые неудобно держать в `OpenSpec`, в одном exec-plan файле или прямо в `src/`.

Из-за этого команды начинают изобретать ad-hoc папки вроде `tasks/roadmap` или складывают process artifacts рядом с кодом задачи.

## Что меняется

- добавить в generated repos project-owned workspace `docs/work-items/`;
- seed-ить `docs/work-items/README.md` и `docs/work-items/TEMPLATE.md` как canonical long-running companion surface;
- обновить generated onboarding и Codex workflow docs так, чтобы они явно различали:
  - `OpenSpec` как contract/change proposal;
  - `bd` как execution tracking;
  - `docs/exec-plans/` как living progress/handoff;
  - `docs/work-items/<task-id>/` как supporting artifacts и task-local evidence;
- расширить static/fixture checks, чтобы canonical routing к new work-item workspace не drift-ил.

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `template-ci-contours`
- Affected code:
  - `scripts/bootstrap/generated-project-surface.sh`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/codex-workflows.md`
  - `scripts/qa/codex-onboard.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `tests/smoke/bootstrap-agents-overlay.sh`
  - `tests/smoke/agent-docs-contract.sh`
  - `tests/smoke/copier-update-ready.sh`
