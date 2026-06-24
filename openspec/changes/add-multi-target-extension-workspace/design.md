## Context
Some 1C extension projects have several deployable extensions and several vendor configuration baselines. A Delans-style workspace needs to develop:

- a shared extension loaded into multiple targets;
- target-specific extensions for UT and UNF;
- reference source dumps for each target configuration release.

The template already has `src/cfe` support and `load-cfe` style contours. The missing piece is a stable target model that lets scripts and agents answer "which configuration source tree and which extensions belong to this target?" even when doing so requires changing the current `src/cf` contract.

## Goals / Non-Goals
- Goal: support `src/cf/<target-id>` as first-class target configuration source trees for generated projects.
- Goal: support an explicit extension matrix, for example `ut22 -> DelansCommon, ES_Логистика`.
- Goal: update source, context, doctor and runtime automation that currently assumes `src/cf` is one configuration source tree.
- Goal: make generated context and doctor output target-aware.
- Non-goal: merge several CFE source trees into one extension.
- Non-goal: support automatic semantic merge of different vendor configuration releases.
- Non-goal: preserve the old `src/cf` semantics for repositories that opt into multi-target mode.

## Decisions
- Decision: use `src/cf/<target-id>` for target configuration source dumps in multi-target repositories.
  - Reason: extension work needs target configuration sources near the deployable 1C source tree, and current automation must become target-aware instead of hiding target configs elsewhere.
- Decision: keep deployable extension sources under `src/cfe/<extension-name>`.
  - Reason: current CFE tooling already uses this shape.
- Decision: add project-owned machine-readable target metadata instead of inferring the matrix from directory names.
  - Reason: an extension can belong to several targets, and names alone cannot encode profile, target release, and check policy.
- Decision: target-aware runtime commands take an explicit `--target <id>` and fail closed when omitted for multi-target-only contours.
  - Reason: implicit target selection is risky when several live infobases exist.

## Risks / Trade-offs
- More metadata must stay fresh.
  - Mitigation: generated context checks fail when target paths or extension matrix entries point to missing directories.
- Large target `cf` dumps can make indexing slow.
  - Mitigation: generated summaries stay compact and tooling supports target selection.
- Existing scripts assume `src/cf` is directly importable.
  - Mitigation: multi-target repositories require explicit `--target`, and legacy direct `src/cf` operations fail closed with a migration message.

## Migration Plan
1. Add target metadata skeletons to generated-project templates.
2. Teach generated context export to discover and summarize `src/cf/*` target configuration roots.
3. Update source and CFE load/check/test contours to require explicit target selection in multi-target mode.
4. Update docs and smoke tests.
5. Add migration guidance for single-target projects that want to move from `src/cf` to `src/cf/<target-id>`.

## Open Questions
- Should target metadata live in one file such as `automation/context/target-matrix.json`, or be split into `src/cf/<id>/target.json` plus an aggregate generated artifact?
- Should target-specific YAxUnit selections be part of runtime profiles or a separate project-owned test matrix?
