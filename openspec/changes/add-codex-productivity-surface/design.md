## Контекст

Source repo уже хорошо покрывает runtime/tooling слой template-а, но Codex onboarding остаётся фрагментированным.
Новый агент быстро видит `README.md` и `Makefile`, однако дальше вынужден сам собирать operational truth из:

- `openspec/project.md`;
- `env/README.md` и `tests/README.md`;
- `.github/workflows/ci.yml`;
- `.claude/skills/README.md`;
- `automation/context/*`, где часть файлов сейчас placeholder-ы;
- `scripts/bootstrap/agents-overlay.sh`, который больше ориентирован на generated projects, чем на сам source repo.

Это особенно заметно в двух местах:

1. Для source repo отсутствует короткий root-level guidance layer, который бы сразу сказал: "это template source repo", "вот authoritative docs", "вот baseline verify command".
2. Машинный контекст и Codex-specific reuse mechanisms выглядят незавершёнными: `.codex/config.toml` содержит только commented examples, а live `automation/context/*` не отражает реальный repo state.

## Цели

- Сократить путь нового Codex-агента до ответа на вопросы:
  - что это за проект;
  - где его entrypoint-ы;
  - как его проверять;
  - какие docs считать authoritative.
- Сделать agent-facing docs системными, а не набором разрозненных файлов.
- Развести truthful source-repo context и template skeletons для generated projects.
- Дать Codex repo-local skills и безопасную `.codex` customization surface.
- Сделать freshness/integrity agent-facing artifacts machine-checkable в static CI contour.

## Не цели

- Не менять runtime semantics launcher-скриптов.
- Не вводить обязательную зависимость на конкретный MCP, semantic index или внешнюю LLM-интеграцию.
- Не разносить инструкции по множеству nested `AGENTS.md` без явной локальной необходимости.
- Не превращать корневой `AGENTS.md` в длинный handbook.

## Решения

### 1. Root `AGENTS.md` остаётся тонким entrypoint, а не encyclopedic document

Корневой `AGENTS.md` должен сохранить managed OpenSpec block и получить короткий source-repo overlay:

- что этот repo является template source, а не прикладным 1С-решением;
- где находится docs index;
- какой baseline verification path запускать первым;
- куда смотреть за архитектурой, review policy и execution plans.

Глубокие инструкции выносятся в `docs/agent/*`.
Nested `AGENTS.md` или `AGENTS.override.md` нужны только там, где есть действительно локальные правила каталога.

### 2. Agent docs строятся как system of record с одним индексом

`docs/agent/index.md` становится главным agent-facing TOC.
Минимальный обязательный набор документов:

- `docs/agent/overview.md` или `docs/agent/architecture.md` с картой top-level зон repo;
- отдельный документ про границу `template source repo vs generated project`;
- `docs/agent/verify.md` с onboarding/baseline/deeper contours;
- `docs/agent/review.md` с repo-specific review criteria;
- `docs/exec-plans/README.md` с правилами для long-running задач.

Root `README.md` и `AGENTS.md` должны ссылаться на этот индекс, а не дублировать его содержимое.

### 3. Live automation context должен быть truthful для source repo

Текущие `automation/context/project-map.md` и `automation/context/metadata-index.json` нельзя просто "исправить под source repo", если template продолжит раздавать их generated projects как будто это их live context.

Поэтому нужно явно развести два класса артефактов:

- live context для самого template source repo;
- template-scoped skeleton artifacts для generated projects.

Практически это означает:

- live `automation/context/*` описывает текущий source repo и не содержит placeholders;
- skeleton context для generated projects хранится в явно template-scoped path или filename, чтобы агент не принимал его за truth в source repo;
- `scripts/llm/export-context.sh` обновляет только live source-repo context и оставляет machine-checkable freshness signal.

### 4. Нужен repo-owned lightweight `agent-verify` contour

Первый verify path для агента не должен вести сразу в тяжёлый `make qa`, который включает BSL-specific contour.

Нужен отдельный repo-owned onboarding target/script, который:

- не требует licensed 1C runtime;
- не требует Java/BSL LS;
- подтверждает целостность OpenSpec/traceability/docs/skills/context;
- при необходимости может включать fixture/smoke checks, которые runnable в обычной dev/CI среде.

`docs/agent/verify.md` должен объяснять:

- baseline verify;
- fixture contour;
- runtime contour;
- когда и зачем переходить на следующий слой.

### 5. Codex-facing reuse должен жить в `.agents/skills` и `.codex`

Для Codex канонический repo-local skill surface должен быть discoverable через `.agents/skills/`.
При этом:

- implementation logic остаётся в `scripts/`;
- `.agents/skills/*` и `.claude/skills/*` работают как thin wrappers/facades;
- единый checked-in intent map описывает, какой user intent куда маршрутизируется;
- `.codex/config.toml` и companion docs остаются host-safe by default: optional MCP examples разрешены, но checked-in config не должен ломать fresh environment.

### 6. Static CI должен проверять freshness agent-facing artifacts

Новый или расширенный static contour должен валидировать:

- root/agent docs index consistency;
- отсутствие placeholder-ов в live context;
- skill bindings для Codex/Claude packaging;
- freshness/generated-state marker для live automation context.

Это делается отдельным repo-owned check script, который можно локально запустить до CI.

### 7. Durable docs не должны зависеть от line-specific links

Линии файлов удобны в аудите и ревью, но они хрупкие для долговременной навигации.

Поэтому system-of-record docs должны использовать:

- file links;
- section anchors;
- явные названия команд и entrypoint-ов.

Line-specific links допускаются только в transient artifacts:

- audit reports;
- review comments;
- traceability/change docs, если они intentionally short-lived или regenerated.

## Рассмотренные альтернативы

### Альтернатива A: расширить только корневой `AGENTS.md`

Отклонено. Это уменьшит initial confusion, но снова превратит root entrypoint в перегруженный документ и не создаст machine-checkable documentation system.

### Альтернатива B: оставить placeholder context, но просто документировать это в README

Отклонено. Агент всё равно воспринимает checked-in machine-readable context как truth. Нужна структурная развязка live context и skeleton artifacts.

### Альтернатива C: считать `make qa` достаточным onboarding path

Отклонено. Для нового агента это misleading entrypoint, потому что он подтягивает более тяжёлый contour, чем нужен для first-pass docs/tooling verification.

### Альтернатива D: ограничиться `.claude/skills/*` и не добавлять Codex-discoverable package

Отклонено. Это не улучшает Codex productivity и оставляет repo-level reuse завязанным на vendor-specific packaging.

## Риски и компромиссы

- Появится больше agent-facing документации, и её придётся поддерживать.
  Митигация: docs index + CI freshness checks + generated/live context split.
- Появится дублирование packaging между `.agents/skills` и `.claude/skills`.
  Митигация: single intent map и rule "logic lives only in repo scripts".
- Если overly broaden static checks, onboarding verify contour снова станет тяжёлым.
  Митигация: жёстко отделить baseline docs/tooling checks от optional heavy QA/runtime contours.

## План миграции

1. Зафиксировать OpenSpec contract для repository agent guidance, Codex skills/customization и static CI checks.
2. Добавить system-of-record docs и root entrypoint routing.
3. Развести live context source repo и template-scoped skeleton context.
4. Добавить repo-local `agent-verify` contour и Codex-discoverable skills/config.
5. Подключить agent-doc/context/skills freshness checks в CI и copier-smoke verification.

## Открытые вопросы

- Нет blocking open questions для proposal stage.
- Во время реализации нужно будет выбрать точный path для generated-project skeleton context, но сам requirement о разделении live/skeleton surfaces уже должен быть зафиксирован сейчас.
