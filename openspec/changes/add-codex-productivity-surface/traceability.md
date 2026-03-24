# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `repository-agent-guidance.repository-level-agent-entry-point` | `AGENTS.md`, `README.md`, `docs/agent/index.md` | `openspec validate add-codex-productivity-surface --strict --no-interactive`, `./scripts/qa/check-agent-docs.sh`, `bash tests/smoke/agent-docs-contract.sh` |
| `repository-agent-guidance.agent-documentation-system-of-record` | `docs/agent/index.md`, `docs/agent/architecture.md`, `docs/agent/source-vs-generated.md`, `docs/agent/verify.md`, `docs/agent/review.md`, `docs/exec-plans/README.md`, `docs/README.md` | `./scripts/qa/check-agent-docs.sh`, `bash tests/smoke/agent-docs-contract.sh` |
| `repository-agent-guidance.truthful-machine-readable-agent-context` | `automation/context/*`, `automation/context/templates/*`, `scripts/llm/export-context.sh` | `./scripts/qa/check-agent-docs.sh`, `make export-context` |
| `repository-agent-guidance.agent-verification-runbook` | `docs/agent/verify.md`, `scripts/qa/agent-verify.sh`, `Makefile`, `tests/smoke/copier-update-ready.sh` | `make agent-verify`, `bash tests/smoke/copier-update-ready.sh` |
| `repository-agent-guidance.versioned-execution-plans-for-long-running-agent-work` | `docs/exec-plans/README.md`, `docs/exec-plans/active/.gitkeep`, `docs/exec-plans/completed/.gitkeep`, `docs/agent/index.md` | `./scripts/qa/check-agent-docs.sh` |
| `project-scoped-skills.project-scoped-skills-package` | `.agents/skills/*`, `.claude/skills/*`, `.claude/skills/README.md` | `./scripts/qa/check-skill-bindings.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `project-scoped-skills.intent-to-capability-mapping` | `.claude/skills/README.md`, `docs/agent/index.md`, `.agents/skills/*` | `./scripts/qa/check-skill-bindings.sh`, `./scripts/qa/check-agent-docs.sh` |
| `project-scoped-skills.repo-local-codex-customization` | `.codex/config.toml`, `.codex/README.md`, `.agents/skills/*` | `./scripts/qa/check-agent-docs.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `template-ci-contours.agent-facing-artifact-freshness` | `.github/workflows/ci.yml`, `scripts/qa/check-agent-docs.sh`, `scripts/qa/check-skill-bindings.sh`, `tests/smoke/agent-docs-contract.sh` | `openspec validate add-codex-productivity-surface --strict --no-interactive`, `./scripts/qa/check-agent-docs.sh`, `bash tests/smoke/agent-docs-contract.sh` |
