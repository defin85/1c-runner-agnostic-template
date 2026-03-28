## Context

Generated repositories currently receive template-managed `src/cf/AGENTS.md` and `src/cf/README.md`.
These files live inside the same tree that `load-src` and direct `ibcmd config import` treat as deployable configuration sources.
Experimental evidence from a generated repo showed that full import from `src/cf` fails with these markdown files present and succeeds when the same tree is copied without them.

The change is intentionally breaking: importable source roots take priority over nested local routing files.

## Goals

- Keep `src/cf` importable as a clean 1C source tree
- Preserve useful agent routing/context outside deployable `src/cf`
- Make `template-update` remove stale legacy files from already generated repositories
- Fail closed if template-managed docs drift back into deployable `src/cf`

## Non-Goals

- Introduce a runtime workaround that sanitizes a copy before import
- Preserve backward compatibility for `src/cf/AGENTS.md` or `src/cf/README.md`
- Rework unrelated generated-project routing surfaces

## Decisions

- Decision: `src/AGENTS.md` becomes the closest template-managed router for `src/**`
  - Rationale: it stays above deployable roots while remaining close to the dense source tree

- Decision: the semantic meaning of `src/cf/README.md` moves into `src/README.md` and generated-project/project-map template docs
  - Rationale: the content is structural guidance, not deployable source payload

- Decision: overlay update gets explicit cleanup for retired legacy files under `src/cf`
  - Rationale: `src/cf/README.md` was previously seeded by bootstrap but not tracked in the overlay manifest, so manifest diff alone cannot remove it from older generated repos

- Decision: QA/smoke checks treat markdown routing artifacts inside `src/cf` as a hard failure
  - Rationale: the contract must protect full importability, not just docs consistency

## Risks / Trade-offs

- Old generated repos lose a formerly local router in `src/cf`
  - Mitigation: move the same routing targets into `src/AGENTS.md` and generated-project docs

- Overlay cleanup could remove user-authored markdown files if the rule is too broad
  - Mitigation: explicitly clean only the retired template paths in update flow, and keep the semantic invariant targeted at forbidden routing artifacts in `src/cf`

## Migration Plan

1. Remove `src/cf/AGENTS.md` and `src/cf/README.md` from the template source.
2. Update generated routing/docs and QA/smoke expectations.
3. Teach overlay update to delete stale `src/cf/AGENTS.md` and `src/cf/README.md`.
4. Document that generated repos should expect those stale files to disappear after `make template-update`.
