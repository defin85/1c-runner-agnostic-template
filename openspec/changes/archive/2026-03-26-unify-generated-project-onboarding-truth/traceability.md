# Трассировка

## Requirement -> Code -> Test

| Requirement | Код | Проверка |
| --- | --- | --- |
| `generated-project-agent-guidance` / Root generated guidance acts as a router | `docs/agent/generated-project-index.md`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/agents-overlay.sh`, `.codex/README.md` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / Codex-first generated runbook | `Makefile`, `scripts/qa/codex-onboard.sh`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `.codex/README.md` | `bash tests/smoke/copier-update-ready.sh`, `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `generated-runtime-support-matrix` / Project-owned runtime support matrix | `scripts/bootstrap/generated-project-surface.sh`, `automation/context/templates/generated-project-runtime-support-matrix.json`, `automation/context/templates/generated-project-runtime-support-matrix.md`, `automation/context/templates/generated-project-project-map.md` | `bash tests/smoke/copier-update-ready.sh`, `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `generated-runtime-support-matrix` / Runtime support matrix drives generated onboarding | `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `scripts/qa/codex-onboard.sh`, `scripts/bootstrap/agents-overlay.sh`, `env/README.md` | `bash tests/smoke/copier-update-ready.sh`, `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `generated-runtime-support-matrix` / Runtime support matrix freshness | `scripts/qa/check-agent-docs.sh`, `scripts/llm/export-context.sh`, `automation/context/templates/generated-project-metadata-index.json`, `automation/context/templates/generated-project-hotspots-summary.md` | `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `generated-context-artifacts` / Semantic agent surface verification | `scripts/qa/check-agent-docs.sh`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/agents-overlay.sh`, `docs/agent/source-vs-generated.md` | `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `runtime-profile-schema` / Canonical local runtime profile layout | `env/README.md`, `automation/context/templates/generated-project-runtime-profile-policy.json`, `scripts/qa/check-agent-docs.sh` | `bash tests/smoke/agent-docs-contract.sh`, `make agent-verify` |
| `template-ci-contours` / Agent-facing ownership verification | `tests/smoke/agent-docs-contract.sh`, `tests/smoke/bootstrap-agents-overlay.sh`, `tests/smoke/copier-update-ready.sh`, `automation/context/template-managed-paths.txt` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |

## Выполненные проверки

- `bash tests/smoke/agent-docs-contract.sh`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `./scripts/llm/export-context.sh --write`
- `openspec validate unify-generated-project-onboarding-truth --strict --no-interactive`
- `make agent-verify`
