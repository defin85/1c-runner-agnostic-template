# Traceability

## runtime-profile-schema

- Runtime profiles expose reusable `platform.xpra`, X11, web diagnostic, CFE and YAxUnit capability knobs without project-specific defaults.
  - Code: `scripts/python/runtime.py`, `scripts/lib/runtime-profile.sh`, `scripts/diag/doctor.sh`, `scripts/adapters/direct-platform.sh`
  - Docs: `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-operator-local-runbook.md`
  - Tests: `tests/smoke/runtime-direct-platform-xpra-contract.sh`, `tests/smoke/web-client-diagnostic-contract.sh`, `tests/smoke/yaxunit-contour-contract.sh`

## ibcmd-capability-drivers

- `ibcmd` helpers validate auth and secret behavior for file infobases and optional empty password use.
  - Code: `scripts/lib/ibcmd.sh`, `scripts/lib/onec.sh`
  - Docs: `automation/context/templates/generated-project-runtime-support-matrix.md`
  - Tests: `tests/smoke/copier-update-ready.sh`

## template-ci-contours

- Template ships reusable operator-local contours for X11 preflight, CFE load/config checks, port lease, web diagnostics, YAxUnit runners, and a mandatory golden-baseline hook.
  - Code: `Makefile`, `scripts/diag/check-x11-contour.sh`, `scripts/platform/load-cfe.sh`, `scripts/platform/configure-cfe-runtime-flags.sh`, `scripts/platform/check-cfe-applicability.sh`, `scripts/platform/check-cfe-config.sh`, `scripts/lib/onec-port-lease.sh`, `scripts/lib/web-client-diagnostic.sh`, `scripts/lib/yaxunit.sh`, `scripts/test/run-web-client-diagnostic.sh`, `scripts/test/run-yaxunit.sh`, `scripts/test/sync-yaxunit-runtime.sh`, `scripts/test/run-yaxunit-warm-service.sh`, `scripts/test/run-golden-baseline.sh`, `tooling/vanessa/run-web-client-diagnostic.mjs`, `tooling/yaxunit/warm_rpc_controller.py`
  - Docs: `automation/context/templates/generated-project-operator-local-runbook.md`, `tests/golden/README.md`
  - Tests: `tests/smoke/runtime-direct-platform-xpra-contract.sh`, `tests/smoke/load-cfe-contract.sh`, `tests/smoke/configure-cfe-runtime-flags-contract.sh`, `tests/smoke/check-cfe-applicability-contract.sh`, `tests/smoke/check-cfe-config-contract.sh`, `tests/smoke/onec-port-lease-contract.sh`, `tests/smoke/web-client-diagnostic-contract.sh`, `tests/smoke/yaxunit-contour-contract.sh`, `tests/smoke/yaxunit-warm-rpc-contour-contract.sh`, `tests/smoke/golden-baseline-contract.sh`

## generated-runtime-support-matrix

- Generated project surfaces advertise the new reusable contours and render them through Copier/update paths.
  - Code: `copier.yml`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/copier-post-copy.sh`, `scripts/bootstrap/copier-post-update.sh`, `scripts/template/lib-overlay.sh`, `scripts/template/update-template.sh`, `scripts/python/template_tools.py`
  - Docs: `automation/context/templates/generated-project-runtime-support-matrix.json`, `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-operator-local-runbook.md`
  - Tests: `tests/smoke/copier-update-ready.sh`, `make agent-verify`
