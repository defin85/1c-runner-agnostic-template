# Template Source Project Map

## Repository Role

- template source repo for generated 1С repositories
- not a business application repository

## Main Capability Areas

- runtime toolkit under `scripts/platform/`, `scripts/diag/`, `scripts/test/`
- template delivery under `copier.yml`, `scripts/bootstrap/`, `scripts/template/`
- agent tooling under `docs/agent/`, `.agents/skills/`, `.claude/skills/`, `.codex/`
- source-of-truth requirements under `openspec/`

## Canonical Entrypoints

- bootstrap: `./scripts/bootstrap/copier-post-copy.sh`, `./scripts/bootstrap/copier-post-update.sh`
- runtime diagnostics: `./scripts/diag/doctor.sh`
- runtime capabilities: `./scripts/platform/*.sh`
- tests: `./scripts/test/*.sh`
- QA and agent checks: `./scripts/qa/*.sh`
- context export preview: `./scripts/llm/export-context.sh --preview`
- context export refresh: `./scripts/llm/export-context.sh --write`

## Canonical Checks

- baseline agent verify: `make agent-verify`
- broader QA: `make qa`
- fixture delivery smoke: `bash tests/smoke/bootstrap-agents-overlay.sh`
- copier delivery smoke: `bash tests/smoke/copier-update-ready.sh`
