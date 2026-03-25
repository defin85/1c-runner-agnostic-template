# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `template-overlay-delivery.bootstrap-uses-copier-copy-only` | `copier.yml`, `scripts/bootstrap/copier-post-copy.sh`, `scripts/template/lib-overlay.sh`, `docs/template-maintenance.md`, `README.md` | `openspec validate replace-copier-updates-with-overlay-releases --strict --no-interactive`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `template-overlay-delivery.generated-repositories-track-overlay-version-separately` | `scripts/template/lib-overlay.sh`, `scripts/bootstrap/copier-post-copy.sh`, `scripts/bootstrap/copier-post-update.sh`, `docs/template-maintenance.md`, `docs/agent/generated-project-index.md`, `scripts/qa/check-agent-docs.sh` | `make agent-verify`, `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `template-overlay-delivery.overlay-apply-uses-only-managed-paths` | `automation/context/template-managed-paths.txt`, `scripts/template/lib-overlay.sh`, `scripts/template/update-template.sh`, `scripts/qa/check-overlay-manifest.sh` | `make agent-verify`, `bash tests/smoke/copier-update-ready.sh` |
| `template-overlay-delivery.overlay-apply-preserves-project-owned-truth` | `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/overlay-post-apply.sh`, `scripts/bootstrap/copier-post-update.sh`, `docs/agent/source-vs-generated.md`, `docs/template-maintenance.md` | `bash tests/smoke/copier-update-ready.sh` |
| `template-overlay-delivery.overlay-maintenance-path-is-documented-and-verified` | `scripts/template/check-update.sh`, `scripts/template/update-template.sh`, `tooling/update-1c-project`, `README.md`, `docs/template-maintenance.md`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `scripts/qa/check-agent-docs.sh` | `make agent-verify`, `bash tests/smoke/update-1c-project-wrapper.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
