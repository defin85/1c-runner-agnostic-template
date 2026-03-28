# Трассировка

## Requirement -> Code -> Test

| Requirement | Код | Проверка |
| --- | --- | --- |
| `agent-runtime-toolkit` / Repo-Owned Diff-Aware Load Wrapper | `scripts/platform/load-diff-src.sh`, `Makefile`, `README.md`, `docs/agent/architecture.md`, `docs/agent/generated-project-verification.md`, `env/README.md`, `scripts/bootstrap/generated-project-surface.sh`, `automation/context/templates/generated-project-operator-local-runbook.md` | `bash tests/smoke/runtime-load-diff-src-contract.sh`, `bash tests/smoke/runtime-load-diff-src-validation-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `agent-runtime-toolkit` / Wrapper publishes machine-readable execution artifacts | `scripts/platform/load-diff-src.sh`, `scripts/lib/capability.sh`, `tests/smoke/runtime-load-diff-src-contract.sh`, `tests/smoke/runtime-load-diff-src-validation-contract.sh` | `bash tests/smoke/runtime-load-diff-src-contract.sh`, `bash tests/smoke/runtime-load-diff-src-validation-contract.sh` |
| `agent-runtime-toolkit` / After filtering there are no eligible source files | `scripts/platform/load-diff-src.sh`, `tests/smoke/runtime-load-diff-src-validation-contract.sh` | `bash tests/smoke/runtime-load-diff-src-validation-contract.sh` |
| `ibcmd-capability-drivers` / Explicit Git-Diff Bridge To Partial Load-Src | `scripts/platform/load-diff-src.sh`, `scripts/platform/load-src.sh`, `tests/smoke/runtime-load-diff-src-contract.sh`, `tests/smoke/runtime-ibcmd-capability-contract.sh` | `bash tests/smoke/runtime-load-diff-src-contract.sh`, `bash tests/smoke/runtime-load-diff-src-validation-contract.sh`, `bash tests/smoke/runtime-ibcmd-capability-contract.sh` |
| `project-scoped-skills` / Intent Mapping For Diff-To-Load Workflow | `.agents/skills/1c-load-diff-src/SKILL.md`, `.claude/skills/1c-load-diff-src/SKILL.md`, `.agents/skills/README.md`, `.claude/skills/README.md`, `automation/context/template-managed-paths.txt`, `scripts/qa/check-agent-docs.sh` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |

## Выполненные проверки

- `openspec validate add-load-diff-src-bridge --strict --no-interactive`
- `bash tests/smoke/runtime-load-diff-src-contract.sh`
- `bash tests/smoke/runtime-load-diff-src-validation-contract.sh`
- `bash tests/smoke/runtime-ibcmd-capability-contract.sh`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
