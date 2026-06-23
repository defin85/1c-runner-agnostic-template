# Runtime Support Matrix Reference

Этот template-scoped reference описывает expected contract для `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.

## Matrix Contract

- project-owned checked-in runtime truth для generated repo;
- различает минимум `supported`, `unsupported`, `operator-local`, `provisioned`;
- покрывает как минимум `codex-onboard`, `agent-verify`, `export-context-check`, `doctor`, `check-x11-contour`, `load-cfe`, `configure-cfe-runtime-flags`, `check-cfe-applicability`, `check-cfe-config`, `load-diff-src`, `load-task-src`, `xunit`, `yaxunit`, `yaxunit-warm-rpc`, `web-client-diagnostic`, `golden-baseline`, `bdd`, `smoke`, `publish-http`;
- classifies template-shipped direct-platform `xunit` contour as `operator-local` when the generated starter surface wires the reusable runner but still needs operator-owned profile values such as ADD root;
- classifies `golden-baseline` as mandatory project regression baseline and keeps it fail-closed until the project wires `tests/golden/run.sh` or `GOLDEN_BASELINE_COMMAND`;
- маршрутизирует `operator-local` contours через `docs/agent/operator-local-runbook.md` или другой явно объявленный project-owned runbook;
- может опционально объявлять `projectSpecificBaselineExtension` для extra no-1C smoke, но не смешивает его с template baseline;
- не использует ignored local-private profile как единственный durable shared source of truth;
- остаётся согласованной с `automation/context/project-map.md`, `docs/agent/generated-project-index.md`, `docs/agent/runtime-quickstart.md` и `docs/agent/generated-project-verification.md`.
