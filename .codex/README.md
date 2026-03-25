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

1. Root `README.md` -> `automation/context/project-map.md` -> `automation/context/metadata-index.generated.json`.
2. `make agent-verify` -> `make export-context-check`.
3. [env/README.md](../env/README.md) для runtime profile contract.
4. [docs/agent/review.md](../docs/agent/review.md) перед code/doc/tooling changes.
5. [.agents/skills/README.md](../.agents/skills/README.md) для repeatable workflows.
6. [docs/exec-plans/README.md](../docs/exec-plans/README.md) для long-running work.

## Closeout

- `local-only`: если writable remote отсутствует или handoff по договорённости локальный, не изобретайте обязательный push; сдайте локальный diff и verification state.
- `remote-backed`: если проект работает через remote, sync и push идут только после локально зелёных quality gates.

## Optional MCP And Config

- `config.toml` здесь intentionally host-safe by default: checked-in MCP examples закомментированы.
- Если включаете локальные MCP servers, адаптируйте пути и env values под свою машину.
- Не делайте machine-specific MCP paths обязательными для команды или CI.

## Useful Session Controls

- `/status` — посмотреть текущую конфигурацию сессии и лимиты.
- `/compact` — свернуть длинную сессию без потери ключевого контекста.
- `/review` — попросить Codex проверить рабочее дерево.
- `/ps` — посмотреть background terminals.
- `/resume` — продолжить сохранённую сессию.
- `/mcp` — увидеть доступные MCP tools.
