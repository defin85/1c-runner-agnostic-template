# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `generated-project-agent-guidance.generated-project-root-entry-point` | `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/agents-overlay.sh`, `docs/agent/generated-project-index.md`, `docs/template-maintenance.md`, `README.md` | `openspec validate add-generated-project-agent-ownership-model --strict --no-interactive`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `generated-project-agent-guidance.update-safe-agent-artifact-ownership` | `docs/agent/source-vs-generated.md`, `docs/template-maintenance.md`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/copier-post-update.sh`, `scripts/qa/check-agent-docs.sh` | `make agent-verify`, `bash tests/smoke/copier-update-ready.sh` |
| `generated-project-agent-guidance.concrete-project-owned-context-seeds` | `scripts/bootstrap/generated-project-surface.sh`, `automation/context/templates/generated-project-project-map.md`, `automation/context/templates/generated-project-metadata-index.json`, `copier.yml` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `generated-project-agent-guidance.verification-matrix-for-generated-repositories` | `docs/agent/generated-project-verification.md`, `scripts/bootstrap/generated-project-surface.sh`, `Makefile` | `make agent-verify`, `bash tests/smoke/copier-update-ready.sh` |
| `generated-project-agent-guidance.side-effect-transparent-context-export` | `scripts/llm/export-context.sh`, `Makefile`, `scripts/qa/check-agent-docs.sh`, `tests/smoke/copier-update-ready.sh` | `make agent-verify`, `bash tests/smoke/copier-update-ready.sh` |
| `template-ci-contours.agent-facing-ownership-verification` | `scripts/qa/check-agent-docs.sh`, `tests/smoke/bootstrap-agents-overlay.sh`, `tests/smoke/copier-update-ready.sh`, `.github/workflows/ci.yml` | `make agent-verify`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
