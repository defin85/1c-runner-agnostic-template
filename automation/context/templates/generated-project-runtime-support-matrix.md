# Runtime Support Matrix Reference

Этот template-scoped reference описывает expected contract для `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.

## Matrix Contract

- project-owned checked-in runtime truth для generated repo;
- различает минимум `supported`, `unsupported`, `operator-local`, `provisioned`;
- покрывает как минимум `codex-onboard`, `agent-verify`, `export-context-check`, `doctor`, `xunit`, `bdd`, `smoke`, `publish-http`;
- не использует ignored local-private profile как единственный durable shared source of truth;
- остаётся согласованной с `automation/context/project-map.md`, `docs/agent/generated-project-index.md` и `docs/agent/generated-project-verification.md`.
