# Codex Repo Guide

Используйте этот каталог как project-scoped companion к root `AGENTS.md`.

## С чего начинать

- Доверьте репозиторий, чтобы Codex подхватил `.codex/config.toml`.
- В source repo начните с [docs/agent/index.md](../docs/agent/index.md).
- В generated project начните с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md).
- В generated project для read-only первого экрана используйте `make codex-onboard`.
- Для первого прогона используйте `make agent-verify`.
- Для generated project дополнительно сверяйтесь с [env/README.md](../env/README.md), [docs/agent/review.md](../docs/agent/review.md), [.agents/skills/README.md](../.agents/skills/README.md) и [docs/exec-plans/README.md](../docs/exec-plans/README.md).
- Repeatable workflows лежат в [.agents/skills/README.md](../.agents/skills/README.md).

## Generated Project First Hour

Если это generated repo, держите порядок таким:

1. `make codex-onboard`.
2. [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md) как canonical onboarding router.
3. `docs/agent/architecture-map.md` и `docs/agent/runtime-quickstart.md` как project-owned code/runtime digests.
4. `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json` как checked-in runtime truth.
5. `make agent-verify` -> `make export-context-check`.
6. `automation/context/metadata-index.generated.json` открывайте только когда compact summary уже не хватает.

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
- Сначала запустите `make codex-onboard`, затем при необходимости откройте `docs/agent/generated-project-index.md`.
- Пройдите `make agent-verify` и `make export-context-check`.
- Перед runtime-работой проверьте [env/README.md](../env/README.md), `automation/context/runtime-profile-policy.json` и `automation/context/runtime-support-matrix.md`.

### Long-Running Change

- Скопируйте [docs/exec-plans/TEMPLATE.md](../docs/exec-plans/TEMPLATE.md) и держите рядом [docs/exec-plans/README.md](../docs/exec-plans/README.md) как contract.
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
