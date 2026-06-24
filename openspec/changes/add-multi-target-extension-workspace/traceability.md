# Traceability

| Requirement | Planned implementation | Verification |
|---|---|---|
| Target source tree contract | `src/cf/<target-id>`, target metadata skeletons, docs | fixture with multiple targets and fail-closed legacy `src/cf` operations |
| Extension-to-target matrix | project-owned matrix file, runtime-support-matrix semantic checks, and generated summaries | smoke test for stale/missing target and extension entries |
| Target-aware runtime profiles | profile validation, doctor diagnostics, and fail-closed runtime wrappers | multi-target smoke with missing profile target and mismatched target checks |
| Target-aware source, CFE and test flow | updated `load-src`, `load-diff-src`, `load-cfe`, applicability/config checks, update-db, `run-xunit`, `run-smoke`, `run-yaxunit`, and warm YAxUnit service | shell smoke with fake targets and dry-run/status summaries |
| Target-aware generated context | `export-context.sh` target inventory and recommended routing | `export-context-check` fixture |
