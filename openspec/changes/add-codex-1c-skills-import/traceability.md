# Traceability

## project-scoped-skills

- Imported compatibility pack from `cc-1c-skills` is delivered as template-managed Codex/Claude skill surfaces
  - Code: `automation/vendor/cc-1c-skills/**`, `.agents/skills/**`, `.claude/skills/**`, `scripts/python/imported_skills.py`, `scripts/skills/run-imported-skill.sh`, `scripts/skills/run-imported-skill.ps1`
  - Docs: `README.md`, `.agents/skills/README.md`, `.claude/skills/README.md`, `automation/vendor/cc-1c-skills/README.md`
  - Tests: `tests/python/test_cross_platform.py`, `tests/smoke/imported-skills-contract.sh`, `tests/smoke/copier-update-ready.sh`, `make agent-verify`

- Imported skills keep a repo-owned execution contract instead of vendored inline runtime snippets
  - Code: `scripts/python/imported_skills.py`, `scripts/python/cli.py`, `.agents/skills/*/SKILL.md`, `.claude/skills/*/SKILL.md`
  - Docs: `.agents/skills/README.md`, `.claude/skills/README.md`
  - Tests: `./scripts/qa/check-skill-bindings.sh`, `python -m unittest tests.python.test_cross_platform`, `bash tests/smoke/imported-skills-contract.sh`

- Imported skill refresh remains reproducible and provenance-aware
  - Code: `scripts/python/imported_skills.py`, `automation/vendor/cc-1c-skills/UPSTREAM.json`, `automation/vendor/cc-1c-skills/imported-skills.json`
  - Docs: `automation/vendor/cc-1c-skills/README.md`
  - Tests: `bash tests/smoke/imported-skills-contract.sh`, `make agent-verify`

## Verification Runs

- `openspec validate add-codex-1c-skills-import --strict --no-interactive`
- `python -m unittest tests.python.test_cross_platform`
- `bash tests/smoke/imported-skills-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
