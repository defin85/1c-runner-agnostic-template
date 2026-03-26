## Контекст

Предыдущие changes уже сделали generated projects заметно безопаснее для агентов:

- root и nested guidance больше не source-repo-centric;
- generated repos получили truthful verification docs, summary-first карту и sanctioned profile policy;
- semantic lint стал достаточно сильным, чтобы ловить placeholder verification и ownership drift.

Следующий незакрытый слой — конкурирующие truth-сигналы:

- onboarding размазан по нескольким entrypoint-ам;
- runtime truth не сведена в один checked-in artifact;
- local-private contour может стать фактической shared truth через project map и runbook;
- новый агент не получает one-command read-only экран для первого часа работы.

## Цели

- Дать generated проекту один canonical onboarding route.
- Дать новому Codex one-command read-only onboarding.
- Зафиксировать runtime support truth в checked-in project-owned matrix вместо неявной ссылки на ignored local profile.
- Закрыть semantic drift на local-private runtime truth механическими checks.

## Не-цели

- Не требуется автоматически выводить domain-specific hotspot map для каждого business context.
- Не требуется реализовывать реальные runtime contours за generated проект.
- Не требуется плодить nested `AGENTS.md` по всему `src/` на уровне шаблона.

## Решения

### 1. Один canonical onboarding router

`docs/agent/generated-project-index.md` становится единственным полным onboarding document.

Остальные входы:

- root `AGENTS.md`
- root `README.md`
- `.codex/README.md`

остаются role-specific pointer-ами и не дублируют линейный маршрут целиком.

Это снижает drift cost и делает semantic lint проще: у generated repo есть один документ, в котором должен жить полный first-hour path.

### 2. Read-only codex-onboard как automation boundary

Нужен отдельный repo-owned command, который:

- не пишет checked-in файлы;
- не требует licensed 1C runtime;
- печатает identity, baseline verify, runtime support statuses, active routers и next commands;
- может использоваться человеком, Codex и fixture smoke как одинаковый read-only entrypoint.

`make codex-onboard` должен быть thin wrapper над `scripts/qa/codex-onboard.sh`.

### 3. Runtime support truth должна быть project-owned и checked-in

Runtime support matrix должна жить в project-owned слое, а не выводиться из ignored local files.

Предлагаемая форма:

- `automation/context/runtime-support-matrix.json` — machine-readable source of truth;
- `automation/context/runtime-support-matrix.md` — human-readable companion для onboarding и review.

Каждый contour описывается минимум через:

- capability id;
- status (`supported`, `unsupported`, `operator-local`, `provisioned`);
- expected profile provenance;
- canonical entrypoint или runbook;
- prerequisites;
- owner / maintenance note.

### 4. Local-private contour допустим, но только как operator-local

Generated проект может иметь рабочий contour только в `env/local.json` или другом ignored profile.
Но тогда durable checked-in docs не могут подавать его как shared baseline truth.

Правильный contract:

- contour отражается в runtime support matrix;
- статус помечается как `operator-local`;
- onboarding и verification docs различают shared checked-in truth и operator-local contour;
- project map не рекламирует такой contour как canonical shared baseline без этой оговорки.

### 5. Semantic lint должен проверять не только layout, но и authoritative truth

`check-agent-docs.sh` и fixture smoke должны валить:

- отсутствие runtime support matrix при наличии runtime claims в project map или runbook;
- stale/cross-file inconsistency между matrix, project map и onboarding docs;
- local-private file как durable shared truth без operator-local classification;
- повторный drift к competing onboarding routers вместо одного canonical document.

## Риски и компромиссы

- Runtime support matrix добавляет новый maintained artifact. Это оправдано только если freshness и consistency будут проверяться механически.
- Слишком жёсткий lint может наказать generated проекты за осознанный operator-local contour. Поэтому статус `operator-local` нужен как first-class classification, а не как warning-only компромисс.
- Если `codex-onboard` начнёт зависеть от write-side context refresh, он потеряет смысл как read-only стартовый entrypoint. Значит, ему нужен строго read-only contract.

## План миграции

1. Сначала зафиксировать canonical onboarding router и runtime support matrix в specs.
2. Затем добавить read-only onboarding command и wiring в generated docs/templates.
3. После этого усилить semantic lint и fixture smoke.
4. В конце сократить дублирующие routers в root entry surfaces.

## Открытые вопросы

- Делать ли `runtime-support-matrix.md` полностью производным от JSON или оставить оба артефакта project-owned с общей freshness-проверкой?
- Нужно ли `codex-onboard` печатать machine-readable JSON режимом (`--json`) сразу в первой версии, или достаточно human-readable default output?
