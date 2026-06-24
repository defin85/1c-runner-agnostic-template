## 1. Implementation
- [x] 1.1 Add project-owned target metadata schema and generated-project skeleton docs for `src/cf/<target-id>`.
- [x] 1.2 Update generated context export to summarize target configuration identities, counts, and extension matrix entries.
- [x] 1.3 Extend runtime profile docs and validation so target-aware contours can bind `--target` to a profile and target metadata entry.
- [x] 1.4 Update source and CFE load/check/update flows so multi-target repositories require explicit target selection.
- [x] 1.5 Add target-aware YAxUnit/runtime-smoke routing for extension workspaces.
- [x] 1.6 Update runtime support matrix templates, onboarding docs, and operator-local runbooks.
- [x] 1.7 Add smoke/fixture tests for missing targets, stale extension matrix entries, and fail-closed legacy `src/cf` operations in multi-target mode.
- [x] 1.8 Run `openspec validate add-multi-target-extension-workspace --strict --no-interactive` and template verification.
