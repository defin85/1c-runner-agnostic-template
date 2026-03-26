# Generated Project Index

Этот документ является стартовой точкой для generated 1С-репозитория, созданного из шаблона `1c-runner-agnostic-template`.
Если вы находитесь в сгенерированном проекте, используйте этот файл вместо source-repo-centric `docs/agent/index.md` как primary onboarding route.

## Быстрый маршрут

1. Запустите `make codex-onboard`, если нужен read-only первый экран новой Codex-сессии.
2. Зафиксируйте project-owned truth по `automation/context/project-map.md`.
3. Откройте `docs/agent/architecture-map.md`, если нужен project-owned ответ на вопрос “где менять X?”.
4. Откройте `docs/agent/runtime-quickstart.md`, если нужен короткий ответ “что здесь можно запустить и с какими prerequisites?”.
5. Сверьтесь с `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`, чтобы подтвердить статусы `supported`, `unsupported`, `operator-local`, `provisioned`.
6. Откройте `automation/context/hotspots-summary.generated.md`, чтобы получить compact summary-first карту hot paths.
7. При необходимости углубитесь в `automation/context/metadata-index.generated.json`, чтобы точнее сузить поиск по `src/`.
8. Пройдите safe-local baseline из [docs/agent/generated-project-verification.md](generated-project-verification.md), [env/README.md](../../env/README.md) и `automation/context/runtime-profile-policy.json`.
9. Если change затрагивает код или agent-facing surface, откройте [docs/agent/review.md](review.md).
10. Для repeatable workflows используйте [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).
11. Если задача длинная, копируйте [docs/exec-plans/TEMPLATE.md](../exec-plans/TEMPLATE.md) и держите рядом [docs/exec-plans/README.md](../exec-plans/README.md).
12. Если работа касается только template refresh, отдельно откройте [docs/template-maintenance.md](../template-maintenance.md).

## Что считается source of truth

| Вопрос | Источник |
| --- | --- |
| Что это за система? | `automation/context/project-map.md` |
| Где искать прикладной change scenario -> code path map? | `docs/agent/architecture-map.md` |
| Где держать короткий runtime digest? | `docs/agent/runtime-quickstart.md` |
| Где лежит checked-in runtime truth? | `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json` |
| Где смотреть optional project-specific baseline extension? | `automation/context/runtime-support-matrix.json`, `docs/agent/runtime-quickstart.md`, `make codex-onboard` |
| Где summary-first карта hot paths? | `automation/context/hotspots-summary.generated.md` |
| Где raw generated-derived inventory? | `automation/context/metadata-index.generated.json` |
| Какие проверки безопасно запускать первыми? | [docs/agent/generated-project-verification.md](generated-project-verification.md) |
| Где смотреть runtime profile contract, local-only profiles и sanctioned checked-in presets? | [env/README.md](../../env/README.md), `automation/context/runtime-profile-policy.json` |
| Где review expectations для docs/tooling changes? | [docs/agent/review.md](review.md) |
| Где repeatable skills и Codex-first runbook? | [.agents/skills/README.md](../../.agents/skills/README.md), [.codex/README.md](../../.codex/README.md) |
| Где вести long-running work? | [docs/exec-plans/README.md](../exec-plans/README.md) |
| Где project-level intent и ограничения? | `openspec/project.md` |
| Где reusable repo entrypoint-ы? | `scripts/` и `Makefile` |
| Где template maintenance path? | [docs/template-maintenance.md](../template-maintenance.md) |

## Codex-First First Hour

Линейный маршрут для новой сессии Codex:

1. Запустите `make codex-onboard`, чтобы собрать identity, safe-local commands, runtime status и следующие команды без записи в repo.
2. Подтвердите curated truth через `automation/context/project-map.md`.
3. Уточните code routing по `docs/agent/architecture-map.md`.
4. Уточните runtime answer по `docs/agent/runtime-quickstart.md`, затем подтвердите его через `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
5. Сверьтесь с `automation/context/hotspots-summary.generated.md`; raw inventory `automation/context/metadata-index.generated.json` открывайте только когда summary уже не хватает.
6. Пройдите safe-local baseline: `make agent-verify`, затем `make export-context-check`.
7. Перед изменениями поведения сверяйтесь с `openspec/project.md` и [docs/agent/review.md](review.md).
8. Для repeatable действий ищите готовый workflow в [.agents/skills/README.md](../../.agents/skills/README.md) и [.codex/README.md](../../.codex/README.md).
9. Для долгих или cross-cutting задач копируйте [docs/exec-plans/TEMPLATE.md](../exec-plans/TEMPLATE.md) и ведите plan artifact по контракту из [docs/exec-plans/README.md](../exec-plans/README.md).

## Codex Controls

- `/plan` — фиксируйте execution matrix до того, как long-running change разрастётся.
- `/compact` — сворачивайте длинную сессию перед handoff или после большого exploration pass.
- `/review` — запускайте focused review перед closeout или отдельной review-only сессией.
- `/ps` — проверяйте фоновые shell/process contours, если параллельно идут doctor/test/export команды.
- `/mcp` — быстро подтверждайте, какие MCP tools реально доступны в текущей сессии.

## Planning Matrix

Короткая формула planning path: `OpenSpec -> bd -> docs/exec-plans/README.md`.

| Когда | Куда идти | Почему |
| --- | --- | --- |
| Новая capability, breaking change, architecture shift, неоднозначный intent | `OpenSpec` | Сначала фиксируется signable contract в `openspec/changes/<id>/`. |
| Approved code work | `bd` | Исполняемый task graph и live tracking после approval. |
| Долгая, multi-session, cross-cutting работа | `docs/exec-plans/TEMPLATE.md` -> `docs/exec-plans/README.md` | Готовый starter artifact и contract для handoff и session controls. |

## Ownership Model

- `template-managed`: `scripts/`, shared docs в `docs/agent/`, `.agents/skills/`, `.claude/skills/`, CI workflow, managed blocks в root docs.
- `seed-once / project-owned`: root `README.md`, `openspec/project.md`, `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/runtime-quickstart.md`, `automation/context/runtime-profile-policy.json`, `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`.
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`, `automation/context/hotspots-summary.generated.md`.
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
