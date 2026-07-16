## 1. Implementation
- [x] 1.1 Add repo-local `scripts/tools/onec-test-port-lease` and update `scripts/lib/onec-port-lease.sh` to prefer it before `PATH`.
- [x] 1.2 Add reusable Vanessa BDD target validation library without project-specific defaults.
- [x] 1.3 Add fail-closed `bdd-warm-service` lifecycle entrypoint and sync entrypoint skeletons.
- [x] 1.4 Update generated runtime matrix JSON/Markdown templates and operator-local runbook starter to include `bdd-warm-service`.
- [x] 1.5 Document the BDD warm-service project-owned inputs: Vanessa Automation Single path, warmup feature, library paths, step definitions, and extension scope.
- [x] 1.6 Add fixture smoke tests for port lease fallback, matrix presence, fail-closed warm-service behavior, and project-specific string audit.
- [x] 1.7 Run `openspec validate add-vanessa-bdd-warm-service-contour --strict --no-interactive` and the relevant template smoke checks.
