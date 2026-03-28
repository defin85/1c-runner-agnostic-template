# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `generated-project-agent-guidance` / `Local Working-Area Routing For Generated Repositories` | `src/AGENTS.md`, `src/README.md`, `docs/agent/generated-project-index.md`, `scripts/bootstrap/generated-project-surface.sh`, `automation/context/template-managed-paths.txt`, `scripts/qa/check-agent-docs.sh` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `./scripts/qa/check-agent-docs.sh` |
| `generated-project-agent-guidance` / `Deployable Main Configuration Root Stays Free Of Routing Docs` | `src/AGENTS.md`, `src/README.md`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/qa/check-agent-docs.sh`, `tests/smoke/agent-docs-contract.sh` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `./scripts/qa/check-agent-docs.sh` |
| `template-overlay-delivery` / `Overlay Update Retires Legacy Source-Root Routing Files` | `scripts/template/update-template.sh`, `scripts/template/lib-overlay.sh`, `scripts/bootstrap/overlay-post-apply.sh`, `scripts/bootstrap/generated-project-surface.sh`, `automation/context/template-managed-paths.txt`, `src/README.md`, `README.md`, `docs/template-maintenance.md`, `tests/smoke/copier-update-ready.sh` | `bash tests/smoke/copier-update-ready.sh` |
| `generated-context-artifacts` / `Semantic Agent Surface Verification` | `scripts/qa/check-agent-docs.sh`, `tests/smoke/agent-docs-contract.sh`, `tests/smoke/bootstrap-agents-overlay.sh`, `tests/smoke/copier-update-ready.sh` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `./scripts/qa/check-agent-docs.sh` |

## Выполненные проверки

- `openspec validate remove-deployable-source-agent-docs --strict --no-interactive`
- `bash tests/smoke/agent-docs-contract.sh`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
