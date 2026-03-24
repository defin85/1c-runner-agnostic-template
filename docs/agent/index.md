# Agent Docs Index

Этот каталог является agent-facing system of record для репозитория.

## Быстрый маршрут

Если вы только вошли в проект:

1. Прочитайте [AGENTS.md](../../AGENTS.md).
2. Откройте [docs/agent/architecture.md](architecture.md).
3. Сверьтесь с [docs/agent/source-vs-generated.md](source-vs-generated.md).
4. Запустите baseline из [docs/agent/verify.md](verify.md).

## Authoritative Map

| Вопрос | Authoritative document |
| --- | --- |
| Что это за репозиторий? | [docs/agent/architecture.md](architecture.md) |
| Чем source repo отличается от generated project? | [docs/agent/source-vs-generated.md](source-vs-generated.md) |
| Какие entrypoint-ы канонические? | [docs/agent/architecture.md](architecture.md) |
| Какой baseline verify запускать первым? | [docs/agent/verify.md](verify.md) |
| Как делать review в этом репозитории? | [docs/agent/review.md](review.md) |
| Где вести long-running execution plans? | [docs/exec-plans/README.md](../exec-plans/README.md) |
| Где лежат repeatable repo skills? | [.agents/skills/README.md](../../.agents/skills/README.md) |
| Где Codex-specific repo guidance? | [.codex/README.md](../../.codex/README.md) |

## Durable Linking Policy

- Для долговременной документации используйте ссылки на файл или раздел.
- Line-specific links допустимы в transient artifacts: audit reports, review comments, traceability и change docs.
- Если документ становится source of truth, line-specific links нужно убирать из него.
