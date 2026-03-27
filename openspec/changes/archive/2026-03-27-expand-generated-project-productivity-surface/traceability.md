# Трассировка

## Requirement -> Code -> Test

| Requirement | Код | Проверка |
| --- | --- | --- |
| `generated-project-agent-guidance` / Codex-first generated runbook | `scripts/qa/codex-onboard.sh`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `.codex/README.md`, `docs/exec-plans/README.md`, `docs/exec-plans/TEMPLATE.md`, `docs/exec-plans/EXAMPLE.md` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / Local working-area routing for generated repositories | `src/AGENTS.md`, `src/cf/AGENTS.md`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/qa/check-agent-docs.sh` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / Project-owned code architecture map | `automation/context/templates/generated-project-architecture-map.md`, `scripts/bootstrap/generated-project-surface.sh`, `docs/agent/generated-project-index.md`, `scripts/llm/export-context.sh` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / Project-specific runtime quick reference | `automation/context/templates/generated-project-runtime-quickstart.md`, `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-runtime-support-matrix.json`, `scripts/bootstrap/generated-project-surface.sh`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / Project-specific baseline extension slot | `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-runtime-support-matrix.json`, `scripts/qa/codex-onboard.sh`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `scripts/qa/check-agent-docs.sh` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-context-artifacts` / Generated metadata captures critical identity and entrypoints | `scripts/llm/export-context.sh`, `automation/context/templates/generated-project-hotspots-summary.md`, `automation/context/templates/generated-project-metadata-index.json`, `automation/context/templates/generated-project-project-map.md` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-context-artifacts` / Semantic agent surface verification | `scripts/qa/check-agent-docs.sh`, `scripts/qa/check-overlay-manifest.sh`, `docs/agent/source-vs-generated.md`, `automation/context/template-managed-paths.txt` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-runtime-support-matrix` / Runtime quick reference stays aligned with matrix | `automation/context/templates/generated-project-runtime-quickstart.md`, `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-runtime-support-matrix.json`, `scripts/qa/check-agent-docs.sh`, `scripts/qa/codex-onboard.sh` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `template-ci-contours` / Agent-facing artifact freshness | `scripts/qa/check-agent-docs.sh`, `scripts/qa/check-overlay-manifest.sh`, `tests/smoke/agent-docs-contract.sh`, `tests/smoke/bootstrap-agents-overlay.sh`, `tests/smoke/copier-update-ready.sh` | `openspec validate expand-generated-project-productivity-surface --strict --no-interactive`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |

## Выполненные проверки

- `./scripts/qa/check-overlay-manifest.sh`
- `openspec validate expand-generated-project-productivity-surface --strict --no-interactive`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `bash tests/smoke/agent-docs-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
