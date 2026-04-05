# Generated Recommended Skills Reference

Этот template-scoped reference описывает expected contract для `automation/context/recommended-skills.generated.md`.

## Recommendation Contract

- остаётся generated-derived, а не project-owned truth;
- показывает compact first-hour subset поверх полного `.agents/skills/README.md`;
- ссылается на `make imported-skills-readiness` и `./scripts/skills/run-imported-skill.sh --readiness` как canonical readiness/bootstrap path для executable imported compatibility skills;
- выводит concrete skill names или repo-owned entrypoints, а не prose-only советы;
- использует repo shape signals вроде subsystems, forms, extensions, reports, external processors и service edges для выбора subset;
- refresh-ится через `./scripts/llm/export-context.sh --write`.
