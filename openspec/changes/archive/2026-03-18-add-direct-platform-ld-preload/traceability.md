# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `runtime-profile-schema.structured-schema-version-2` | `env/wsl.example.json`, `env/README.md`, `README.md`, `scripts/lib/runtime-profile.sh`, `scripts/lib/onec.sh` | `bash tests/smoke/runtime-direct-platform-ld-preload-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `openspec validate add-direct-platform-ld-preload --strict --no-interactive` |
| `runtime-profile-schema.redacted-launcher-artifacts` | `scripts/lib/capability.sh`, `scripts/lib/onec.sh`, `scripts/diag/doctor.sh`, `scripts/adapters/direct-platform.sh` | `bash tests/smoke/runtime-direct-platform-ld-preload-contract.sh`, `bash tests/smoke/runtime-doctor-contract.sh` |
| `agent-runtime-toolkit.adapter-friendly-runtime-model` | `scripts/adapters/direct-platform.sh`, `scripts/lib/capability.sh`, `scripts/lib/onec.sh`, `scripts/platform/create-ib.sh`, `scripts/test/run-xunit.sh`, `env/wsl.example.json`, `README.md`, `env/README.md` | `bash tests/smoke/runtime-capability-contract.sh`, `bash tests/smoke/runtime-direct-platform-ld-preload-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
