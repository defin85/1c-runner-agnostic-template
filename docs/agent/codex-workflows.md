# Codex Workflows

Этот документ является canonical Codex workflow guide для generated repo.
Используйте его после того, как первый router уже подтвердил repo identity через `docs/agent/generated-project-index.md` и `make codex-onboard`.

## Planning Path

Базовая формула: `OpenSpec -> bd -> docs/exec-plans/TEMPLATE.md`.

| Когда | Куда идти | Что считать результатом |
| --- | --- | --- |
| Анализ, новая capability, breaking change, architecture shift, ambiguous intent | `OpenSpec` | signable contract в `openspec/changes/change-id/` |
| Approved code work | `bd` | executable task graph, live status и closeout state |
| Long-running / multi-session / cross-cutting work | `docs/exec-plans/TEMPLATE.md` + `docs/exec-plans/README.md` | living plan artifact для handoff и restart |

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
2. Ведите progress, surprises, decisions и outcomes в одном living file.
3. Используйте `/plan` в начале и `/compact` перед handoff.

### Review-Only

1. Откройте `docs/agent/review.md`.
2. Используйте `/review`, если нужен focused review без новой реализации.
3. Не считайте `tasks.md`, Beads status или comments доказательством реализации без чтения кода и tests.

## Skills And MCP

- Repeatable repo-owned entrypoints описаны в `.agents/skills/README.md`.
- `.codex/README.md` остаётся коротким companion для repo trust, config и pointers.
- Operator-local runtime decisions держите в `docs/agent/operator-local-runbook.md`.
- Full runtime contract и sanctioned profile policy живут в `env/README.md` и `automation/context/runtime-profile-policy.json`.
