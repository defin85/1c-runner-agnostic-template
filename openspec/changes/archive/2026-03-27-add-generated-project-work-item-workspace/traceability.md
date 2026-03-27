# Трассировка

## Requirement -> Задачи -> Фактическое доказательство

| Requirement | Задачи | Фактическое доказательство |
| --- | --- | --- |
| `generated-project-agent-guidance` / codex-first runbook | 1.2, 2.1 | generated onboarding различает `OpenSpec`, `bd`, `docs/exec-plans/` и `docs/work-items/` в canonical router, workflow doc и `make codex-onboard` |
| `generated-project-agent-guidance` / project-owned work-item workspace | 1.1, 1.2, 2.1, 2.2 | generated repos seed-ят `docs/work-items/README.md` и `docs/work-items/TEMPLATE.md` как project-owned companion surface и не рекламируют ad-hoc папки вроде `tasks/roadmap` |
| `template-ci-contours` / freshness и ownership для long-running companion workspace | 2.2, 3.1, 3.2 | static + fixture contours валят missing, stale или ownership-drift для `docs/work-items/` routing, manifest и generated-derived context |

## Requirement -> Код -> Тест

| Requirement | Код | Тест |
| --- | --- | --- |
| `generated-project-agent-guidance` / codex-first runbook | `scripts/bootstrap/generated-project-surface.sh`, `docs/agent/generated-project-index.md`, `docs/agent/codex-workflows.md`, `scripts/qa/codex-onboard.sh`, `scripts/bootstrap/agents-overlay.sh`, `.codex/README.md`, `docs/agent/index.md`, `docs/agent/architecture.md`, `docs/agent/source-vs-generated.md` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify` |
| `generated-project-agent-guidance` / project-owned work-item workspace | `scripts/bootstrap/generated-project-surface.sh`, `automation/context/templates/generated-project-work-items-readme.md`, `automation/context/templates/generated-project-work-items-template.md`, `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md`, `scripts/llm/export-context.sh`, `automation/context/templates/generated-project-metadata-index.json`, `automation/context/templates/generated-project-hotspots-summary.md` | `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `template-ci-contours` / freshness и ownership | `scripts/qa/check-agent-docs.sh`, `scripts/qa/check-overlay-manifest.sh`, `copier.yml`, `automation/context/template-managed-paths.txt`, `tests/smoke/agent-docs-contract.sh`, `tests/smoke/copier-update-ready.sh` | `./scripts/qa/check-agent-docs.sh`, `./scripts/qa/check-overlay-manifest.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `openspec validate add-generated-project-work-item-workspace --strict --no-interactive`, `make agent-verify` |
