# Codex Workflows

Этот документ является canonical Codex workflow guide для generated repo.
Используйте его после того, как первый router уже подтвердил repo identity через `docs/agent/generated-project-index.md` и `make codex-onboard`.

## Planning Path

Базовая формула: `OpenSpec -> bd -> docs/exec-plans/TEMPLATE.md -> docs/work-items/README.md`.

| Когда | Куда идти | Что считать результатом |
| --- | --- | --- |
| Анализ, новая capability, breaking change, architecture shift, ambiguous intent | `OpenSpec` | signable contract в `openspec/changes/change-id/` |
| Approved code work | `bd` | executable task graph, live status и closeout state |
| Long-running / multi-session / cross-cutting work | `docs/exec-plans/TEMPLATE.md` + `docs/exec-plans/README.md` | living plan artifact для handoff и restart |
| Bulky task-local inputs, extracted notes, evidence | `docs/work-items/README.md` + `docs/work-items/TEMPLATE.md` | supporting artifacts рядом с exec-plan, но вне tracker-а и вне `src/` |

## Session Controls

- `/plan` — зафиксировать execution matrix до того, как change разрастётся.
- `/compact` — свернуть длинную сессию перед handoff или после большого exploration pass.
- `/review` — запустить focused review pass по текущему worktree.
- `/ps` — проверить фоновые shell/runtime contours.
- `/mcp` — быстро увидеть доступные MCP tools и не гадать про availability.

## Generated Project Flows

### Analysis-Only

1. `make codex-onboard`
2. `docs/agent/generated-project-index.md`
3. `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/runtime-quickstart.md`
4. `automation/context/project-delta-hotspots.generated.md`, затем `automation/context/hotspots-summary.generated.md`

### Approved Code Work

1. Подтвердите, нужен ли `OpenSpec` или достаточно existing spec/project contract.
2. После approval переведите работу в `bd`.
3. Перед coding соберите `Requirement -> Code -> Test`.
4. Для verification используйте `docs/agent/generated-project-verification.md`, runtime support matrix и project-owned runbooks.

### Long-Running Work

1. Скопируйте `docs/exec-plans/TEMPLATE.md`.
2. Если задаче нужны bulky supporting artifacts, скопируйте `docs/work-items/TEMPLATE.md` в папку вида `docs/work-items/task-12345/index.md`.
3. Держите progress, surprises, decisions и outcomes в exec-plan, а extracted notes, attachment summaries и task-local evidence — в `docs/work-items/task-12345/`.
4. Используйте `/plan` в начале и `/compact` перед handoff.

### Review-Only

1. Откройте `docs/agent/review.md`.
2. Используйте `/review`, если нужен focused review без новой реализации.
3. Не считайте `tasks.md`, Beads status или comments доказательством реализации без чтения кода и tests.

## Skills And MCP

- Repeatable repo-owned entrypoints описаны в `.agents/skills/README.md`.
- `.codex/README.md` остаётся коротким companion для repo trust, config и pointers.
- Operator-local runtime decisions держите в `docs/agent/operator-local-runbook.md`.
- Long-running task artifacts держите в `docs/work-items/README.md`, а не в ad-hoc папках вроде `tasks/roadmap`.
- Full runtime contract и sanctioned profile policy живут в `env/README.md` и `automation/context/runtime-profile-policy.json`.
