# Codex Repo Guide

Используйте этот каталог как project-scoped companion к root `AGENTS.md`.

## С чего начинать

- Доверьте репозиторий, чтобы Codex подхватил `.codex/config.toml`.
- В source repo начните с [docs/agent/index.md](../docs/agent/index.md).
- В generated project начните с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md).
- Для первого прогона используйте `make agent-verify`.
- Repeatable workflows лежат в [.agents/skills/README.md](../.agents/skills/README.md).

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
