# Трассировка

## Requirement -> Задачи -> Фактическое доказательство

| Requirement | Задачи | Фактическое доказательство |
| --- | --- | --- |
| `template-overlay-delivery` / Source template release publishing is explicit | 1.1, 1.2, 1.3, 3.3 | source repo публикует `v0.3.6` только через `./scripts/release/publish-overlay-release.sh --tag ...`, а manual push `refs/tags/v*` режется `.githooks/pre-push` |
| `repository-agent-guidance` / Agent documentation system of record | 2.1, 2.2, 2.3 | source docs маршрутизируют в `docs/template-release.md` как в отдельный source release runbook без встраивания manual в root entrypoints |
| `template-ci-contours` / Agent-facing ownership verification | 3.1, 3.2 | smoke/static checks валят drift между release docs, hook workflow, copier exclusions и canonical release command |

## Requirement -> Code -> Test

| Requirement | Code | Test |
| --- | --- | --- |
| `template-overlay-delivery` / Source template release publishing is explicit | `scripts/release/install-source-hooks.sh`, `scripts/release/publish-overlay-release.sh`, `scripts/release/lib-source-release.sh`, `.githooks/pre-push`, `docs/template-release.md` | `bash tests/smoke/template-release-workflow.sh`, `make agent-verify` |
| `repository-agent-guidance` / Agent documentation system of record | `docs/agent/index.md`, `docs/agent/architecture.md`, `docs/agent/verify.md`, `docs/template-maintenance.md`, `docs/template-release.md`, `automation/context/template-source-project-map.md`, `automation/context/template-source-metadata-index.json` | `./scripts/qa/check-agent-docs.sh`, `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `template-ci-contours` / Agent-facing ownership verification | `scripts/qa/check-agent-docs.sh`, `scripts/qa/check-overlay-manifest.sh`, `copier.yml`, `.github/workflows/ci.yml`, `tests/smoke/copier-update-ready.sh`, `tests/smoke/template-release-workflow.sh` | `bash tests/smoke/copier-update-ready.sh`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/template-release-workflow.sh`, `openspec validate add-source-template-release-workflow --strict --no-interactive` |
