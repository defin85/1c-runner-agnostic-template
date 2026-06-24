## Context

Generated repositories already receive:

- generic capability launcher `./scripts/test/run-xunit.sh`
- repo-owned env contract for profile-defined `command`
- starter doc `tests/xunit/README.md`

But they do not receive a runnable xUnit contour, a harness skeleton, or a canonical loop for synchronizing fresh `src/cf` changes into the runtime before running xUnit.

## Goals

- Ship one reusable direct-platform xUnit contour that generated repositories can use immediately after wiring operator-local paths in a local profile.
- Make the starter harness server-side only so template baseline does not depend on managed forms.
- Provide one canonical local loop for TDD on `src/cf` changes.
- Keep unsupported adapters and unsupported delta shapes fail-closed.

## Non-Goals

- Do not ship a remote-windows xUnit contour in this change.
- Do not make xUnit a safe-local baseline contour.
- Do not hide full-source reload fallback inside the wrapper.

## Decisions

### Decision: xUnit baseline stays operator-local

The shipped contour requires operator-owned profile fields such as platform paths and ADD root. Therefore generated runtime truth must classify `xunit` as `operator-local`, not `supported`.

### Decision: direct-platform runner is template-managed

The template now ships:

- `./scripts/test/run-xunit-direct-platform.sh`
- `./scripts/test/build-xunit-epf.sh`
- `tests/xunit/smoke.quickstart.json`
- `src/epf/TemplateXUnitHarness`

The outer launcher `./scripts/test/run-xunit.sh` remains the generic capability boundary.

### Decision: harness is server-side only

The generic harness uses only `Ext/ObjectModule.bsl` and no managed form. This avoids the UI-startup hangs that a form-based default harness can trigger in local direct-platform xUnit contours.

### Decision: canonical TDD loop is explicit and fail-closed

`./scripts/test/tdd-xunit.sh` becomes the canonical convenience wrapper for local development:

1. detect git-backed `src/cf` changes
2. if there are add/modify/untracked changes, run `load-diff-src`
3. run `update-db`
4. run `xunit`

If the delta contains delete/rename-style changes that `load-diff-src` cannot safely replay, the wrapper stops with an explicit message and points to the manual full-sync path instead of inventing a fallback.

## Risks / Trade-offs

- Example profiles remain operator-local and still need user edits before they become runnable on a machine.
- The wrapper optimizes for the common add/modify TDD path and intentionally rejects unsupported delta shapes instead of silently switching to a slower full reload.

## Verification Strategy

- Smoke/fixture checks for generated surface and doc/runtime truth
- Shell smoke for the new wrapper contract
- OpenSpec validation
- `make agent-verify`
