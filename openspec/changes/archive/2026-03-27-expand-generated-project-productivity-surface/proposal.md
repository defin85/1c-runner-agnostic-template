# Change: generated-project productivity surface

## Why

Generated repos, созданные из шаблона, уже быстро объясняют process-layer и safe-local baseline, но всё ещё дают слишком высокий first-hour cost внутри плотных прикладных зон вроде `src/cf`.
Шаблону не хватает reusable scaffolding для project-owned code navigation, runtime quick answers, long-running workflow bootstrap и machine-checkable freshness для curated truth.

## What Changes

- добавить project-owned scaffolds для `docs/agent/architecture-map.md` и `docs/agent/runtime-quickstart.md` в generated repos;
- углубить generated-project routing внутрь `src/cf` и раньше surfaced Codex session controls в read-only onboarding;
- добавить ready-to-use exec-plan template и минимальный example artifact вместо README-only contract;
- ввести documented project-specific baseline extension slot для optional no-1C smoke;
- расширить semantic/static checks на curated truth freshness, broken references и consistency между runtime matrix, runtime quick reference, project map и onboarding.

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `generated-runtime-support-matrix`
  - `template-ci-contours`
- Affected code:
  - `automation/context/templates/**`
  - `docs/agent/**`
  - `docs/exec-plans/**`
  - `scripts/qa/codex-onboard.sh`
  - `scripts/qa/check-agent-docs.sh`
  - generated `src/cf/AGENTS.md`
