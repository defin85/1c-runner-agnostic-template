# Agent Docs Index

Этот каталог является agent-facing system of record для репозитория.
Если high-level overview в `README.md`, `docs/README.md` или `openspec/project.md` короче либо частично пересекается с этим слоем, для onboarding приоритет у `docs/agent/`.

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
| Что получает generated project как стартовый onboarding set? | [docs/agent/generated-project-index.md](generated-project-index.md) |
| Какие entrypoint-ы канонические? | [docs/agent/architecture.md](architecture.md) |
| Какой baseline verify запускать первым? | [docs/agent/verify.md](verify.md) |
| Как делать review в этом репозитории? | [docs/agent/review.md](review.md) |
| Где вести long-running execution plans? | [docs/exec-plans/README.md](../exec-plans/README.md) |
| Где лежат repeatable repo skills? | [.agents/skills/README.md](../../.agents/skills/README.md) |
| Где Codex-specific repo guidance? | [.codex/README.md](../../.codex/README.md) |
| Где описан isolated template maintenance path для generated repos? | [docs/template-maintenance.md](../template-maintenance.md) |

## Durable Linking Policy

- Для долговременной документации используйте ссылки на файл или раздел.
- Line-specific links допустимы в transient artifacts: audit reports, review comments, traceability и change docs.
- Если документ становится source of truth, line-specific links нужно убирать из него.
