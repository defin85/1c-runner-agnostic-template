# Runtime Support Matrix Reference

Этот template-scoped reference описывает expected contract для `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.

## Matrix Contract

- project-owned checked-in runtime truth для generated repo;
- различает минимум `supported`, `unsupported`, `operator-local`, `provisioned`;
- содержит отдельные записи `linux` и `windows` для каждой возможности и класс доказательства `contract-only` либо `contract-plus-live`;
- требует для `supported` + `contract-plus-live` отпечаток платформы/runtime, время замера и непросроченный срок действия;
- проверяет согласованность Markdown с JSON по точной паре «возможность/платформа»;
- для multi-target extension workspace ссылается на checked-in `automation/context/target-matrix.json`, а не на ignored local profile как единственный источник target truth;
- target-aware entries для `load-cfe`, `check-cfe-applicability`, `check-cfe-config`, `load-diff-src`, `load-task-src`, `smoke` и `update-db` перечисляют target ids или явно ссылаются на extension set из `target-matrix.json`;
- покрывает как минимум `codex-onboard`, `agent-verify`, `export-context-check`, `doctor`, `check-x11-contour`, `load-cfe`, `configure-cfe-runtime-flags`, `check-cfe-applicability`, `check-cfe-config`, `load-diff-src`, `load-task-src`, `yaxunit`, `yaxunit-warm-rpc`, `web-client-diagnostic`, `golden-baseline`, `bdd`, `bdd-warm-service`, `smoke`, `publish-http`;
- classifies `golden-baseline` as mandatory project regression baseline and keeps it fail-closed until the project wires `tests/golden/run.sh` or `GOLDEN_BASELINE_COMMAND`;
- classifies `bdd-warm-service` as `operator-local` or `unsupported`; the template launcher starts `/TESTMANAGER` and `/TestClient`, while project-owned 1С code must handle `capabilities.bddWarmService.launchParameterName`;
- requires explicit `init-test-tooling`, `install-test-tooling`, profile setup and extension sync before YAxUnit or Vanessa BDD runtime runs; Vanessa Automation Single lives at `.artifacts/testing/vanessa/1.2.043.28/vanessa-automation-single.epf`;
- маршрутизирует `operator-local` contours через `docs/agent/operator-local-runbook.md` или другой явно объявленный project-owned runbook;
- может опционально объявлять `projectSpecificBaselineExtension` для extra no-1C smoke, но не смешивает его с template baseline;
- не использует ignored local-private profile как единственный durable shared source of truth;
- остаётся согласованной с `automation/context/project-map.md`, `docs/agent/generated-project-index.md`, `docs/agent/runtime-quickstart.md` и `docs/agent/generated-project-verification.md`.
