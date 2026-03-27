# Change: refine-generated-project-curated-truth

## Почему

Последнее ревью target repo подтвердило, что шаблон уже хорошо решает first-hour mechanics, но reusable agent-facing surface всё ещё теряет время на трёх местах:

- generated root surfaces и Codex workflow guidance частично дублируют друг друга вместо одного canonical workflow doc;
- operator-local runtime decision path размазан между несколькими документами и не даёт одного короткого ответа на вопрос “что реально runnable локально?”;
- generated-derived summary остаётся слишком platform-first и не даёт reusable project-delta слой, который помогал бы быстро находить project-specific hotspots;
- static checks уже сильные, но ещё не удерживают в синхроне curated workflow doc, operator-local runbook и generated project-delta artifact.

## Что меняется

- Добавляется один canonical `docs/agent/codex-workflows.md` для generated repo, а root pointers и onboarding router сокращаются до role-specific маршрутизации.
- Добавляется project-owned scaffold `docs/agent/operator-local-runbook.md` для contour-ов вроде `xunit`, `doctor` и других operator-local ответов.
- Добавляется project-owned hint surface для project-specific delta и generated-derived artifact с project-delta hotspots, который export flow сможет строить рядом с общим summary.
- Усиливаются semantic/static checks и fixture smoke на curated-truth freshness, canonical workflow routing, operator-local runbook и project-delta consistency.

## Влияние

- Затронутые specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `generated-runtime-support-matrix`
  - `template-ci-contours`
- Затронутый код:
  - generated onboarding docs и `.codex/README.md`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `scripts/llm/export-context.sh`
  - `scripts/qa/codex-onboard.sh`
  - `scripts/qa/check-agent-docs.sh`
  - fixture smoke вокруг generated overlay/update path
