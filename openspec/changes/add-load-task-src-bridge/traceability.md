# Трассировка

## Requirement -> Code -> Test

| Requirement | Код | Проверка |
| --- | --- | --- |
| `agent-runtime-toolkit` / Repo-Owned Task-Scoped Load Wrapper | `scripts/platform/load-task-src.sh`, `scripts/platform/load-src.sh`, `scripts/lib/capability.sh`, `Makefile`, `README.md`, `docs/agent/architecture.md`, `docs/agent/generated-project-verification.md`, `env/README.md`, `automation/context/templates/generated-project-runtime-support-matrix.json`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/diag/doctor.sh`, `.github/workflows/ci.yml` | `bash tests/smoke/runtime-load-task-src-contract.sh`, `bash tests/smoke/runtime-load-task-src-validation-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh`, `bash tests/smoke/runtime-ibcmd-doctor-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `agent-runtime-toolkit` / Wrapper publishes machine-readable selection artifacts | `scripts/platform/load-task-src.sh`, `tests/smoke/runtime-load-task-src-contract.sh`, `tests/smoke/runtime-load-task-src-validation-contract.sh` | `bash tests/smoke/runtime-load-task-src-contract.sh`, `bash tests/smoke/runtime-load-task-src-validation-contract.sh` |
| `ibcmd-capability-drivers` / Explicit Commit-Scoped Bridge To Partial Load-Src | `scripts/platform/load-task-src.sh`, `scripts/platform/load-src.sh`, `scripts/git/task-trailers.sh`, `scripts/lib/ibcmd.sh`, `scripts/diag/doctor.sh`, `tests/smoke/runtime-load-task-src-contract.sh`, `tests/smoke/runtime-load-task-src-validation-contract.sh`, `tests/smoke/runtime-ibcmd-capability-contract.sh`, `tests/smoke/runtime-doctor-contract.sh`, `tests/smoke/runtime-ibcmd-doctor-contract.sh` | `bash tests/smoke/runtime-load-task-src-contract.sh`, `bash tests/smoke/runtime-load-task-src-validation-contract.sh`, `bash tests/smoke/runtime-ibcmd-capability-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh`, `bash tests/smoke/runtime-ibcmd-doctor-contract.sh` |
| `project-scoped-skills` / Intent Mapping For Task-To-Load Workflow | `.agents/skills/1c-load-task-src/SKILL.md`, `.claude/skills/1c-load-task-src/SKILL.md`, `.agents/skills/README.md`, `.claude/skills/README.md`, `scripts/bootstrap/agents-overlay.sh`, `docs/agent/generated-project-index.md`, `automation/context/template-managed-paths.txt`, `scripts/qa/check-agent-docs.sh`, `.github/workflows/ci.yml`, `tests/smoke/copier-update-ready.sh` | `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| Repo-owned trailer helper/validation surface | `scripts/git/task-trailers.sh`, `tests/smoke/git-task-trailer-contract.sh`, `tests/smoke/runtime-load-task-src-contract.sh` | `bash tests/smoke/git-task-trailer-contract.sh`, `bash tests/smoke/runtime-load-task-src-contract.sh` |

## Выполненные проверки

- `openspec validate add-load-task-src-bridge --strict --no-interactive`
- `bash tests/smoke/runtime-load-task-src-contract.sh`
- `bash tests/smoke/runtime-load-task-src-validation-contract.sh`
- `bash tests/smoke/git-task-trailer-contract.sh`
- `bash tests/smoke/runtime-doctor-contract.sh`
- `bash tests/smoke/runtime-ibcmd-doctor-contract.sh`
- `bash tests/smoke/runtime-ibcmd-capability-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make export-context-write`
- `make agent-verify`
