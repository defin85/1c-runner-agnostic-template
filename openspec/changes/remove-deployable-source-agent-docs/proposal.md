# Change: remove-deployable-source-agent-docs

## Why

Template-managed `src/cf/AGENTS.md` and `src/cf/README.md` pollute the deployable 1C source tree in generated repositories.
For repositories that use `src/cf` as `sourceDir`, these files break full `ibcmd config import` from the canonical repo-owned `load-src` path.

## What Changes

- **BREAKING** stop shipping `src/cf/AGENTS.md` and `src/cf/README.md` in the template-managed/generated surface
- move useful routing/context for the main configuration above the deployable tree into `src/AGENTS.md`, `src/README.md`, and generated-project docs/templates
- add an explicit overlay-update cleanup path that removes stale `src/cf/AGENTS.md` and `src/cf/README.md` from generated repositories created by older template versions
- add fail-closed QA/smoke checks that reject agent/docs routing artifacts inside importable `src/cf`

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `template-overlay-delivery`
- Affected code:
  - `src/AGENTS.md`
  - `src/README.md`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `scripts/bootstrap/overlay-post-apply.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `scripts/qa/check-overlay-manifest.sh`
  - `tests/smoke/copier-update-ready.sh`
  - `tests/smoke/bootstrap-agents-overlay.sh`
  - `automation/context/template-managed-paths.txt`
