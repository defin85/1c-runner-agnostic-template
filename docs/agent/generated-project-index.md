# Generated Project Index

Этот документ является стартовой точкой для generated 1С-репозитория, созданного из шаблона `1c-runner-agnostic-template`.
Если вы находитесь в сгенерированном проекте, используйте этот файл вместо source-repo-centric `docs/agent/index.md` как primary onboarding route.

## Быстрый маршрут

1. Запустите `make codex-onboard`, если нужен read-only первый экран новой Codex-сессии.
2. Зафиксируйте project-owned truth по `automation/context/project-map.md`.
3. Откройте `docs/agent/architecture-map.md`, если нужен project-owned ответ на вопрос “где менять X?”.
4. Если вопрос упирается в local-private/runtime contour, откройте `docs/agent/operator-local-runbook.md`.
5. Откройте `docs/agent/runtime-quickstart.md`, если нужен короткий ответ “что здесь можно запустить и с какими prerequisites?”.
6. Сверьтесь с `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`, чтобы подтвердить статусы `supported`, `unsupported`, `operator-local`, `provisioned`.
7. Если проект уже описал свои customization selectors, откройте `automation/context/project-delta-hotspots.generated.md`.
8. Откройте `automation/context/hotspots-summary.generated.md`, чтобы получить compact summary-first карту hot paths.
9. При необходимости углубитесь в `automation/context/metadata-index.generated.json`, чтобы точнее сузить поиск по `src/`.
10. Для Codex-native workflow after the first router step откройте [docs/agent/codex-workflows.md](codex-workflows.md).
11. Пройдите safe-local baseline из [docs/agent/generated-project-verification.md](generated-project-verification.md), [env/README.md](../../env/README.md) и `automation/context/runtime-profile-policy.json`.
12. Если change затрагивает код или agent-facing surface, откройте [docs/agent/review.md](review.md).
13. Для repeatable workflows используйте [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).
14. Если задача длинная, копируйте [docs/exec-plans/TEMPLATE.md](../exec-plans/TEMPLATE.md) и держите рядом [docs/work-items/README.md](../work-items/README.md) как companion workspace для supporting artifacts.
15. Если работа касается только template refresh, отдельно откройте [docs/template-maintenance.md](../template-maintenance.md).

## Что считается source of truth

| Вопрос | Источник |
| --- | --- |
| Что это за система? | `automation/context/project-map.md` |
| Где искать прикладной change scenario -> code path map? | `docs/agent/architecture-map.md` |
| Где лежит canonical Codex workflow guide? | `docs/agent/codex-workflows.md` |
| Где принимать решение по operator-local contour-ам? | `docs/agent/operator-local-runbook.md` |
| Где держать короткий runtime digest? | `docs/agent/runtime-quickstart.md` |
| Где лежит checked-in runtime truth? | `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json` |
| Где смотреть optional project-specific baseline extension? | `automation/context/runtime-support-matrix.json`, `docs/agent/runtime-quickstart.md`, `make codex-onboard` |
| Где смотреть project-specific delta hotspots? | `automation/context/project-delta-hotspots.generated.md`, `automation/context/project-delta-hints.json` |
| Где summary-first карта hot paths? | `automation/context/hotspots-summary.generated.md` |
| Где raw generated-derived inventory? | `automation/context/metadata-index.generated.json` |
| Какие проверки безопасно запускать первыми? | [docs/agent/generated-project-verification.md](generated-project-verification.md) |
| Где смотреть runtime profile contract, local-only profiles и sanctioned checked-in presets? | [env/README.md](../../env/README.md), `automation/context/runtime-profile-policy.json` |
| Где review expectations для docs/tooling changes? | [docs/agent/review.md](review.md) |
| Где repeatable skills и Codex-first runbook? | [.agents/skills/README.md](../../.agents/skills/README.md), [.codex/README.md](../../.codex/README.md) |
| Где вести long-running living progress? | [docs/exec-plans/README.md](../exec-plans/README.md), [docs/exec-plans/TEMPLATE.md](../exec-plans/TEMPLATE.md) |
| Где держать bulky task-local artifacts и extracted notes? | [docs/work-items/README.md](../work-items/README.md), [docs/work-items/TEMPLATE.md](../work-items/TEMPLATE.md) |
| Где project-level intent и ограничения? | `openspec/project.md` |
| Где reusable repo entrypoint-ы? | `scripts/` и `Makefile` |
| Где template maintenance path? | [docs/template-maintenance.md](../template-maintenance.md) |

## Codex-First First Hour

Линейный маршрут для новой сессии Codex:

1. Запустите `make codex-onboard`, чтобы собрать identity, safe-local commands, runtime status и следующие команды без записи в repo.
2. Подтвердите curated truth через `automation/context/project-map.md`.
3. Уточните code routing по `docs/agent/architecture-map.md`.
4. Если runtime contour operator-local, сначала откройте `docs/agent/operator-local-runbook.md`, затем подтвердите answer через `docs/agent/runtime-quickstart.md` и `automation/context/runtime-support-matrix.md` / `.json`.
5. Если проект уже знает stable customization selectors, сначала откройте `automation/context/project-delta-hotspots.generated.md`, а уже потом `automation/context/hotspots-summary.generated.md`.
6. Raw inventory `automation/context/metadata-index.generated.json` открывайте только когда curated и summary-first layers уже не хватает.
7. Для детальных Codex-native workflows переходите в [docs/agent/codex-workflows.md](codex-workflows.md).
8. Пройдите safe-local baseline: `make agent-verify`, затем `make export-context-check`.
9. Перед изменениями поведения сверяйтесь с `openspec/project.md` и [docs/agent/review.md](review.md).
10. Если работа становится multi-session, скопируйте [docs/exec-plans/TEMPLATE.md](../exec-plans/TEMPLATE.md) и держите supporting artifacts через [docs/work-items/README.md](../work-items/README.md).
11. Для repeatable действий ищите готовый workflow в [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).

## Planning Matrix

Короткая формула planning path: `OpenSpec -> bd -> docs/exec-plans/TEMPLATE.md -> docs/work-items/README.md`.

| Когда | Куда идти | Почему |
| --- | --- | --- |
| Новая capability, breaking change, architecture shift, неоднозначный intent | `OpenSpec` | Сначала фиксируется signable contract в `openspec/changes/<id>/`. |
| Approved code work | `bd` | Исполняемый task graph и live tracking после approval. |
| Долгая, multi-session, cross-cutting работа | `docs/exec-plans/TEMPLATE.md` -> `docs/exec-plans/README.md` | Living progress, handoff и session restart в одном файле. |
| Bulky task-local evidence, extracted notes, attachment summaries | `docs/work-items/README.md` -> `docs/work-items/TEMPLATE.md` | Supporting artifacts рядом с exec-plan, но вне `OpenSpec` и вне `src/`. |

## Ownership Model

- `template-managed`: `scripts/`, shared docs в `docs/agent/`, `.agents/skills/`, `.claude/skills/`, CI workflow, managed blocks в root docs.
- `seed-once / project-owned`: root `README.md`, `openspec/project.md`, `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/operator-local-runbook.md`, `docs/agent/runtime-quickstart.md`, `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md`, `automation/context/project-delta-hints.json`, `automation/context/runtime-profile-policy.json`, `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`.
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`, `automation/context/hotspots-summary.generated.md`, `automation/context/project-delta-hotspots.generated.md`.
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
