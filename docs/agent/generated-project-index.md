# Generated Project Index

Этот документ является стартовой точкой для generated 1С-репозитория, созданного из шаблона `1c-runner-agnostic-template`.
Если вы находитесь в сгенерированном проекте, используйте этот файл вместо source-repo-centric `docs/agent/index.md` как primary onboarding route.

## Быстрый маршрут

1. Прочитайте root `README.md`.
2. Откройте `automation/context/project-map.md`.
3. Сверьтесь с `automation/context/metadata-index.generated.json`, чтобы быстро сузить поиск по `src/`.
4. Пройдите safe-local baseline из [docs/agent/generated-project-verification.md](generated-project-verification.md) и [env/README.md](../../env/README.md).
5. Если change затрагивает код или agent-facing surface, откройте [docs/agent/review.md](review.md).
6. Для repeatable workflows используйте [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).
7. Если задача длинная, заведите plan в [docs/exec-plans/README.md](../exec-plans/README.md).
8. Если работа касается только template refresh, отдельно откройте [docs/template-maintenance.md](../template-maintenance.md).

## Что считается source of truth

| Вопрос | Источник |
| --- | --- |
| Что это за система? | `automation/context/project-map.md` |
| Где быстрый generated-derived inventory? | `automation/context/metadata-index.generated.json` |
| Какие проверки безопасно запускать первыми? | [docs/agent/generated-project-verification.md](generated-project-verification.md) |
| Где смотреть runtime profile contract и local-only profiles? | [env/README.md](../../env/README.md) |
| Где review expectations для docs/tooling changes? | [docs/agent/review.md](review.md) |
| Где repeatable skills и Codex-first runbook? | [.agents/skills/README.md](../../.agents/skills/README.md), [.codex/README.md](../../.codex/README.md) |
| Где вести long-running work? | [docs/exec-plans/README.md](../exec-plans/README.md) |
| Где project-level intent и ограничения? | `openspec/project.md` |
| Где reusable repo entrypoint-ы? | `scripts/` и `Makefile` |
| Где template maintenance path? | [docs/template-maintenance.md](../template-maintenance.md) |

## Codex-First First Hour

Линейный маршрут для новой сессии Codex:

1. Зафиксируйте identity репозитория по root `README.md`, `automation/context/project-map.md` и `automation/context/metadata-index.generated.json`.
2. Пройдите safe-local baseline: `make agent-verify`, затем `make export-context-check`.
3. Перед изменениями поведения сверяйтесь с `openspec/project.md` и [docs/agent/review.md](review.md).
4. Для runtime contours уточните profile contract в [env/README.md](../../env/README.md).
5. Для repeatable действий ищите готовый workflow в [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).
6. Для долгих или cross-cutting задач создавайте plan artifact в [docs/exec-plans/README.md](../exec-plans/README.md).

## Ownership Model

- `template-managed`: `scripts/`, shared docs в `docs/agent/`, `.agents/skills/`, `.claude/skills/`, CI workflow, managed blocks в root docs.
- `seed-once / project-owned`: root `README.md`, `openspec/project.md`, `automation/context/project-map.md`.
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`.
- `local-private`: `env/local.json`, `env/wsl.json`, `env/ci.json`, `env/windows-executor.json`, `env/.local/*.json`, machine-specific Codex/MCP overrides и секреты.

## Closeout Semantics

- `local-only`: если репозиторий не имеет writable remote или работа договорённо остаётся локальной, завершайте сессию локальным diff, результатами проверок и явным указанием, что push path отсутствует.
- `remote-backed`: если у репозитория есть рабочий remote и команда ожидает публикацию изменений, handoff включает sync/push после зелёных quality gates.
- Не подменяйте `local-only` closeout обязательным `git push` только потому, что такой шаг бывает нужен в template source repo или в другом проекте.

## Ожидаемое поведение template maintenance

- `make template-update` может обновлять только `template-managed` слой и managed blocks.
- `make template-check-update` сверяет `.template-overlay-version` с доступным release ref без записи в репозиторий.
- Если root `AGENTS.md` или `README.md` отсутствует, template update должен восстановить generated-project entry surface перед refresh managed overlay/router.
- Project-owned identity и доменная карта не должны silently перетираться шаблоном.
- Generated-derived inventory refresh-ится явной командой `./scripts/llm/export-context.sh --write`.
- Template maintenance не является primary feature-delivery workflow и не заменяет project-owned changes.
