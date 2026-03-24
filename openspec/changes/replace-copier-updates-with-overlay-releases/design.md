## Context

Шаблон уже разделяет `template-managed`, `project-owned`, `generated-derived` и `local-private` артефакты. Однако delivery path для `template-managed` слоя всё ещё использует `copier update`, то есть механизм, который по своей природе рассчитан на reconciliation template evolution и subproject evolution.

Для generated 1С-репозиториев это создаёт неверный operational pressure:

- churn в `src/**` влияет на стоимость maintenance path, хотя template этими путями не владеет;
- `.copier-answers.yml` и `_commit` становятся operational state для ongoing updates, хотя они нужны главным образом для bootstrap provenance;
- docs обещают `copier update` как канонический путь, хотя desired ownership model предполагает отсутствие project-specific правок в wrapper-layer.

## Goals / Non-Goals

- Goals:
  - оставить `copier copy` единственным bootstrap-механизмом;
  - перевести ongoing updates на versioned overlay apply/check flow;
  - гарантировать, что apply path работает только по manifest template-managed paths;
  - сохранить generated-surface refresh после apply;
  - сделать update contract доказуемым fixture smoke без участия большого `src/**`.
- Non-Goals:
  - строить полноценную external artifact registry или GitHub Releases публикацию;
  - отказываться от `.copier-answers.yml` как bootstrap provenance;
  - менять project-owned политику для `README.md`, `openspec/project.md`, `automation/context/project-map.md`.

## Decisions

- Decision: ongoing updates больше не используют `copier update`.
  - Why: это единственный надёжный способ отрезать maintenance path от churn в product source tree.

- Decision: versioned overlay materialize-ится из template git ref/tag, а не из заранее опубликованного бинарного release asset.
  - Why: этого достаточно для перехода на overlay-модель без внешней release-инфраструктуры.
  - Consequence: tagged template versions остаются каноническим release unit.

- Decision: generated repo хранит отдельный checked-in overlay version file.
  - Why: `_commit` в `.copier-answers.yml` больше не должен быть источником истины для ongoing updates.

- Decision: apply path использует manifest template-managed paths.
  - Why: ownership boundary должен быть явным, проверяемым и независимым от содержимого `src/**`.

- Decision: post-update bootstrap hook переименовывать необязательно; важнее переиспользовать existing generated-surface refresh logic в общем post-apply path.
  - Why: это минимизирует churn в уже проверенной логике README/AGENTS/context regeneration.

## Alternatives Considered

- Продолжать использовать `copier update` и пытаться ужесточить `_exclude`.
  - Rejected: не убирает reconciliation cost большого subproject.

- Shadow `copier update` в временном staging repo.
  - Rejected: сохраняет часть benefits Copier, но создаёт неестественную и труднее объяснимую operational модель.

- Split repo через `git submodule`.
  - Rejected: решает performance-проблему, но резко повышает операционную сложность, хотя target-репозитории в идеале не должны править wrapper-layer вообще.

## Risks / Trade-offs

- Нужно поддерживать manifest template-managed paths.
  - Mitigation: явные smoke/QA checks на drift и обязательное использование manifest в apply path.

- Generated projects могут иметь historical drift в wrapper-layer.
  - Mitigation: apply path должен fail-closed на dirty worktree и честно документировать ownership policy.

- Переход ломает старый mental model `copier update`.
  - Mitigation: сохранить прежние make-target names, но сменить их semantics и явно переписать docs/runbooks.

## Migration Plan

1. Ввести manifest и overlay version file.
2. Реализовать overlay materialize/apply/check scripts.
3. Перевести existing make/tooling wrappers на overlay semantics.
4. Переписать docs/generated onboarding под bootstrap-only Copier.
5. Обновить smoke/QA контуры.
6. Выпустить tagged template version; generated repos дальше обновляются через overlay apply.
