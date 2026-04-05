# Traceability

## generated-project-agent-guidance

- `Codex-First Generated Runbook` and `Generated Repo AI-Readiness Routing` are implemented through a read-only onboarding surface with compact AI-readiness routing
  - Code: `scripts/python/qa.py`, `scripts/qa/codex-onboard.sh`, `scripts/qa/codex-onboard.ps1`
  - Docs: `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `automation/context/templates/generated-project-recommended-skills.md`
  - Tests: `python -m unittest tests.python.test_cross_platform`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`

- `Concrete Project-Owned Context Seeds` are implemented through repo-derived bootstrap/update generation for generated-project starter docs
  - Code: `scripts/bootstrap/generated-project-surface.sh`, `scripts/bootstrap/generated-project-surface.ps1`, `scripts/python/qa.py`
  - Docs: `automation/context/templates/generated-project-project-map.md`, `automation/context/templates/generated-project-architecture-map.md`, `automation/context/templates/generated-project-runtime-quickstart.md`
  - Tests: `bash tests/smoke/bootstrap-agents-overlay.sh`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`

## generated-context-artifacts

- `Generated Metadata Captures Critical Identity And Entrypoints` is implemented through generated metadata, summary, and recommendation refresh paths
  - Code: `scripts/llm/export-context.sh`, `scripts/llm/export-context.ps1`, `scripts/python/context.py`
  - Docs: `automation/context/templates/generated-project-metadata-index.json`, `automation/context/templates/generated-project-hotspots-summary.md`, `automation/context/templates/generated-project-recommended-skills.md`
  - Tests: `python -m unittest tests.python.test_cross_platform`, `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`

- `Generated Skill Recommendation Artifact` is implemented through `recommended-skills.generated.md` refresh and freshness verification
  - Code: `scripts/llm/export-context.sh`, `scripts/python/context.py`, `scripts/python/qa.py`
  - Docs: `automation/context/templates/generated-project-recommended-skills.md`, `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`
  - Tests: `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify`

## project-scoped-skills

- `Intent-To-Capability Mapping` and native-preference discovery are implemented through generated recommendation routing and imported-skill metadata
  - Code: `scripts/python/imported_skills.py`, `scripts/llm/export-context.sh`
  - Docs: `.agents/skills/README.md`, `.claude/skills/README.md`, `automation/context/templates/generated-project-recommended-skills.md`
  - Tests: `bash tests/smoke/imported-skills-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `python -m unittest tests.python.test_cross_platform`

- `Imported Executable Skill Readiness Contract` is implemented through repo-owned dispatcher readiness checks and fail-closed dependency messaging
  - Code: `scripts/skills/run-imported-skill.sh`, `scripts/skills/run-imported-skill.ps1`, `scripts/python/imported_skills.py`, `scripts/python/qa.py`
  - Docs: `docs/agent/generated-project-index.md`, `docs/agent/generated-project-verification.md`, `env/README.md`
  - Tests: `bash tests/smoke/imported-skills-contract.sh`, `python -m unittest tests.python.test_cross_platform`, `make agent-verify`

- `Project-Aware Recommended Skill Subset` is implemented through generated-derived first-hour recommendations mapped from repo shape
  - Code: `scripts/llm/export-context.sh`, `scripts/bootstrap/generated-project-surface.sh`, `scripts/python/qa.py`
  - Docs: `automation/context/templates/generated-project-recommended-skills.md`, `docs/agent/generated-project-index.md`, `automation/context/templates/generated-project-project-map.md`
  - Tests: `bash tests/smoke/agent-docs-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `make agent-verify`

## Verification Runs

- `openspec validate improve-generated-repo-ai-readiness --strict --no-interactive`
- `python -m unittest tests.python.test_cross_platform`
- `bash tests/smoke/imported-skills-contract.sh`
- `bash tests/smoke/bootstrap-agents-overlay.sh`
- `bash tests/smoke/agent-docs-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
