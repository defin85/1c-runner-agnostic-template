# Traceability

## generated-project-agent-guidance

- Template-shipped operator-local xUnit contour for generated repositories
  - Code: `scripts/test/run-xunit-direct-platform.sh`, `scripts/test/build-xunit-epf.sh`, `scripts/test/tdd-xunit.sh`, `src/epf/TemplateXUnitHarness/**`, `tests/xunit/smoke.quickstart.json`
  - Docs: `docs/agent/generated-project-verification.md`, `env/README.md`, `tests/xunit/README.md`, `src/epf/README.md`
  - Tests: `tests/smoke/template-xunit-contour-contract.sh`, `tests/smoke/copier-update-ready.sh`, `tests/smoke/agent-docs-contract.sh`

## generated-runtime-support-matrix

- Generated runtime truth advertises template-shipped xUnit contour as operator-local
  - Code: `scripts/bootstrap/generated-project-surface.sh`, `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-runtime-support-matrix.json`
  - Docs: `docs/agent/generated-project-verification.md`, `automation/context/templates/generated-project-operator-local-runbook.md`, `automation/context/templates/generated-project-runtime-quickstart.md`
  - Tests: `tests/smoke/copier-update-ready.sh`, `scripts/qa/check-agent-docs.sh`

## runtime-profile-schema

- Direct-platform example profiles expose the shipped repo-owned xUnit command and required helper fields
  - Code: `env/local.example.json`, `env/wsl.example.json`, `env/ci.example.json`, `env/windows-executor.example.json`
  - Docs: `env/README.md`, `README.md`
  - Tests: `tests/smoke/copier-update-ready.sh`, `tests/smoke/agent-docs-contract.sh`
