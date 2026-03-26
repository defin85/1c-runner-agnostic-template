## Context

Generated repos уже живут в модели `template-check-update` / `template-update`, но source repo ещё не имеет такого же явного release surface.
Нужен workflow, который:

- не превращает любой локальный commit в публичный overlay release;
- не зависит от устной договорённости “просто не push-ить tag случайно”;
- остаётся простым для maintainer-а и проверяемым в smoke.

## Goals

- дать source repo явный repo-owned command для публикации нового overlay tag;
- отделить обычный branch push от intentional tag push через hook-based guardrail;
- документировать source release path отдельно от generated-project maintenance path;
- проверить workflow механически.

## Non-Goals

- автоматизировать выпуск release notes или GitHub Release;
- делать auto-tagging на каждый merge;
- менять generated-project update semantics.

## Decisions

- Decision: source release path будет explicit command, а не “ручной `git tag && git push`”.
  - Rationale: release должен быть намеренным act-ом, а не побочным эффектом обычного Git workflow.
- Decision: guardrail будет жить в repo-owned `pre-push` hook и блокировать push `refs/tags/v*`, если он идёт не из release command.
  - Rationale: это закрывает accidental `git push --follow-tags` и случайный ручной push существующего локального tag.
- Decision: release command сам запускает baseline verification и проверяет `origin/main` перед publish.
  - Rationale: overlay release должен выходить только из верифицированного и уже опубликованного source state.
- Decision: source release docs выносятся в отдельный runbook, а index/architecture только маршрутизируют туда.
  - Rationale: root/source onboarding не должен разрастаться в release manual.

## Risks / Trade-offs

- Hook требует явной установки и может быть пропущен на машине maintainer-а.
  - Mitigation: repo-owned install command, docs и smoke должны фиксировать ожидаемый `core.hooksPath`.
- Release command становится ещё одним surface, который надо поддерживать.
  - Mitigation: отдельный smoke contour и минимальный scope команды.

## Verification Plan

- smoke на direct tag push block;
- smoke на successful guarded publish в temp repo;
- `make agent-verify`;
- `openspec validate add-source-template-release-workflow --strict --no-interactive`.
