## Context

Шаблон уже умеет bootstrap-ить generated repo и обновлять `template-managed` слой через overlay releases, но generated-project agent surface всё ещё собирается из shared template-managed docs, nested instructions и generated-derived artifacts, которые проектировались вокруг source repo и лишь частично адаптированы под generated repos.

Это создаёт три класса проблем:

- agent routing: shared docs в `docs/` и nested instructions в `automation/` дают conflicting entrypoints и source-centric wording в generated repo;
- context quality: generated-derived artifacts не отражают critical identity и захватывают `local-private` noise;
- verification quality: текущие QA checks ловят broken links и placeholders, но не валидируют semantic drift и operational truth.

## Goals / Non-Goals

- Goals:
  - сделать generated repo legible для нового агента без wide grep по огромному `src/cf`;
  - гарантировать, что shared template-managed docs и nested instructions не ломают generated-project-first onboarding;
  - улучшить quality bar для generated-derived context artifacts и agent-doc checks;
  - явно разделить local-only и remote-backed closeout semantics.
- Non-Goals:
  - пытаться автоматически описать бизнес-домен generated repo;
  - превращать template source docs в encyclopedic knowledge base;
  - менять overlay release lifecycle или runtime capabilities.

## Decisions

- Decision: использовать directory-local instruction files как routing layer, а не как source of truth про конкретный бизнес-домен generated repo.
  - Why: shared files живут и в source repo, и в generated repos, поэтому они должны уметь маршрутизировать, а не подменять project-owned truth.

- Decision: generated root guidance остаётся коротким router-слоем, а detail-heavy workflows живут в linked docs.
  - Why: активный instruction context должен помогать immediate navigation, а не тратить окно загрузки на длинные описания.

- Decision: generated-derived artifacts должны быть privacy-safe и useful-by-default.
  - Why: machine-readable context оправдан только если он ускоряет понимание репозитория и не тащит machine-local шум.

- Decision: semantic QA checks должны валидировать operational truth generated repo, а не только markdown shape.
  - Why: иначе зелёный `make agent-verify` не означает, что новый агент действительно получит правильную mental model.

## Alternatives Considered

- Оставить shared docs как есть и обогащать только `automation/context/project-map.md`.
  - Rejected: это не решает конфликт entrypoints и nested instruction chain.

- Удалить source-centric docs из generated repos полностью.
  - Rejected: generated repos всё ещё получают shared template-managed docs, часть из которых полезна и должна оставаться общей.

- Полностью перенести generated-project guidance в project-owned docs.
  - Rejected: template должен поставлять baseline onboarding, verification и maintenance contract из коробки.

## Risks / Trade-offs

- Чем больше routing layers, тем выше риск противоречий между ними.
  - Mitigation: ввести explicit ownership и mechanical semantic checks.

- Более богатый generated-derived inventory может стать шумным или дорогим в обновлении.
  - Mitigation: ограничить его actionable categories и проверять only critical fields/paths.

- Local-only closeout semantics могут разойтись между source repo и generated repos.
  - Mitigation: валидировать closeout contract against git remote presence там, где это возможно через fixture smoke.

## Migration Plan

1. Переписать generated-project routing в shared docs и nested instruction files.
2. Обновить generated onboarding/runbook и Codex-first guidance.
3. Усилить `export-context.sh` и checked-in generated artifacts.
4. Добавить semantic QA checks и fixture drift cases.
5. Прогнать baseline verify и smoke.
