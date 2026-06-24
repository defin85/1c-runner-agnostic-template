# Traceability

| Requirement | Planned implementation | Verification |
|---|---|---|
| Vanessa BDD warm-service matrix entry | generated runtime matrix starters, operator-local runbook, runtime quickstart | `tests/smoke/vanessa-bdd-warm-service-contract.sh`, `tests/smoke/copier-update-ready.sh` |
| Vanessa BDD target contract | `automation/context/operator-local-targets.json`, runtime profile validation in warm-service entrypoint | missing-target and configured-skeleton smoke cases |
| Repo-local port lease helper fallback | `scripts/tools/onec-test-port-lease`, `scripts/lib/onec-port-lease.sh` lookup order | port lease fallback smoke in warm-service contract |
| Warm-service fixture contract | fail-closed lifecycle entrypoint and project-string audit | `tests/smoke/vanessa-bdd-warm-service-contract.sh` |
