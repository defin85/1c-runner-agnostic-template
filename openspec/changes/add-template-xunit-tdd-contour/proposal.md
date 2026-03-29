# Change: add-template-xunit-tdd-contour

## Why

Шаблон декларирует `TDD` и поставляет launcher slot `./scripts/test/run-xunit.sh`, но generated repositories по умолчанию получают только `unsupportedReason` и starter-doc без живого xUnit contour.
Это вынуждает каждый проект заново собирать runtime path, harness shape и loop `load-src -> update-db -> run-xunit`, хотя именно этот слой должен быть reusable template-owned baseline.

## What Changes

- ship template-managed direct-platform xUnit contour для generated repositories: repo-owned runner, EPF build helper, starter config и generic server-side harness
- добавить canonical local TDD wrapper, который синхронизирует git-backed `src/cf` diff, делает `update-db` и затем запускает xUnit contour
- перевести generated-project truth surfaces и example profiles с `xunit=unsupported` на template-shipped `operator-local` contour там, где profile использует direct-platform
- сохранить fail-closed semantics для unsupported adapters и для delete/rename delta shape, который не может безопасно пройти через `load-diff-src`
- добавить smoke/QA coverage для shipped contour shape, starter surface и generated docs/runtime truth

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-runtime-support-matrix`
  - `runtime-profile-schema`
- Affected code:
  - `Makefile`
  - `scripts/test/run-xunit-direct-platform.sh`
  - `scripts/test/build-xunit-epf.sh`
  - `scripts/test/tdd-xunit.sh`
  - `src/epf/TemplateXUnitHarness/**`
  - `tests/xunit/smoke.quickstart.json`
  - `env/*.example.json`
  - `env/README.md`
  - `docs/agent/generated-project-verification.md`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `tests/smoke/copier-update-ready.sh`
  - `tests/smoke/agent-docs-contract.sh`
