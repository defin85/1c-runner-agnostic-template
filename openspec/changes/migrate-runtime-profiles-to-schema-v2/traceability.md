# Traceability Matrix

## Requirement -> Code -> Test

| Requirement | Code / artifacts | Verification |
| --- | --- | --- |
| `runtime-profile-schema.structured-schema-version-2` | `env/*.example.json`, `env/README.md`, `README.md`, `scripts/lib/runtime-profile.sh`, `scripts/lib/onec.sh`, `scripts/platform/*`, `scripts/test/*`, `scripts/diag/doctor.sh` | `bash tests/smoke/runtime-capability-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh`, `openspec validate migrate-runtime-profiles-to-schema-v2 --strict --no-interactive` |
| `runtime-profile-schema.secret-indirection` | `env/*.example.json`, `env/README.md`, `README.md`, `scripts/lib/onec.sh`, `scripts/diag/doctor.sh`, `.github/workflows/ci.yml` | `bash tests/smoke/runtime-capability-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh` |
| `runtime-profile-schema.schema-version-2-only-gate` | `scripts/lib/runtime-profile.sh`, `scripts/platform/*`, `scripts/test/*`, `scripts/diag/doctor.sh` | `bash tests/smoke/runtime-profile-legacy-rejection.sh`, `bash tests/smoke/runtime-capability-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh` |
| `runtime-profile-schema.migration-support-for-existing-projects` | `docs/migrations/runtime-profile-v2.md`, `scripts/template/migrate-runtime-profile-v2.sh`, `README.md`, `env/README.md`, `tests/smoke/copier-update-ready.sh` | `bash tests/smoke/runtime-profile-migration-helper.sh`, `bash tests/smoke/copier-update-ready.sh` |
| `runtime-profile-schema.redacted-launcher-artifacts` | `scripts/lib/capability.sh`, `scripts/lib/onec.sh`, `scripts/diag/doctor.sh` | `bash tests/smoke/runtime-capability-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh` |
