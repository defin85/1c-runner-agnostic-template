# Traceability

| Requirement | Code | Verification |
| --- | --- | --- |
| `xpra` cleanup | `scripts/adapters/direct-platform.sh` | `tests/smoke/runtime-direct-platform-xpra-contract.sh` |
| warmed BDD event log and completion contract | `scripts/test/run-bdd-warm-run.sh`, `scripts/test/run-bdd-warm-service.sh` | `tests/smoke/vanessa-bdd-warm-service-contract.sh` |
| PostgreSQL golden snapshots | `scripts/test/run-golden-baseline.sh`, `tests/golden/*.sh`, `Makefile` | `tests/smoke/golden-baseline-contract.sh` |
