# Codex Repo Guide

Используйте этот каталог как project-scoped companion к root `AGENTS.md`.

## С чего начинать

- Доверьте репозиторий, чтобы Codex подхватил `.codex/config.toml`.
- В source repo начните с [docs/agent/index.md](../docs/agent/index.md).
- В generated project начните с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md).
- Для первого прогона используйте `make agent-verify`.
- Для generated project дополнительно сверяйтесь с [env/README.md](../env/README.md), [docs/agent/review.md](../docs/agent/review.md), [.agents/skills/README.md](../.agents/skills/README.md) и [docs/exec-plans/README.md](../docs/exec-plans/README.md).
- Repeatable workflows лежат в [.agents/skills/README.md](../.agents/skills/README.md).

## Generated Project First Hour

Если это generated repo, держите порядок таким:

1. Root `README.md` -> `automation/context/project-map.md` -> `automation/context/hotspots-summary.generated.md`.
2. `make agent-verify` -> `make export-context-check`.
3. [env/README.md](../env/README.md) и `automation/context/runtime-profile-policy.json` для runtime profile contract и sanctioned checked-in presets.
4. [docs/agent/review.md](../docs/agent/review.md) перед code/doc/tooling changes.
5. [.agents/skills/README.md](../.agents/skills/README.md) для repeatable workflows.
6. [docs/exec-plans/README.md](../docs/exec-plans/README.md) для long-running work.
7. `automation/context/metadata-index.generated.json` открывайте только когда compact summary уже не хватает.

## Closeout

- `local-only`: если writable remote отсутствует или handoff по договорённости локальный, не изобретайте обязательный push; сдайте локальный diff и verification state.
- `remote-backed`: если проект работает через remote, sync и push идут только после локально зелёных quality gates.

## Optional MCP And Config

- `config.toml` здесь intentionally host-safe by default: checked-in MCP examples закомментированы.
- Если включаете локальные MCP servers, адаптируйте пути и env values под свою машину.
- Не делайте machine-specific MCP paths обязательными для команды или CI.

## Generated Project Playbooks

### First 15 Minutes

- Соберите identity через `README.md`, `automation/context/project-map.md`, `automation/context/hotspots-summary.generated.md`.
- Пройдите `make agent-verify` и `make export-context-check`.
- Перед runtime-работой проверьте [env/README.md](../env/README.md) и `automation/context/runtime-profile-policy.json`.

### Long-Running Change

- Откройте [docs/exec-plans/README.md](../docs/exec-plans/README.md) и заведите plan artifact до того, как сессия разрастётся.
- Используйте `/plan` для фиксации execution matrix и `/compact` перед handoff или длинной веткой исследования.

### Runtime Investigation

- Начинайте с `./scripts/diag/doctor.sh --profile ... --run-root ...`.
- Если contour project-specific и ещё не wired, ожидайте fail-closed `unsupported`, а не зелёный успех.
- `/ps` полезен, когда параллельно идут несколько долгих shell contours.

### Review-Only Session

- Перед review откройте [docs/agent/review.md](../docs/agent/review.md).
- Используйте `/review`, когда нужен focused pass по текущему worktree без новой реализации.

### Parallel Research

- Worktrees и bounded subagents уместны, когда нужно независимо исследовать разные зоны вроде `src/`, runtime contract и docs surface.
- `/agent` и worktrees используйте только для действительно независимых веток исследования, а не вместо локального чтения пары файлов.

## Useful Session Controls

- `/status` — посмотреть текущую конфигурацию сессии и лимиты.
- `/compact` — свернуть длинную сессию без потери ключевого контекста.
- `/review` — попросить Codex проверить рабочее дерево.
- `/ps` — посмотреть background terminals.
- `/resume` — продолжить сохранённую сессию.
- `/mcp` — увидеть доступные MCP tools.
