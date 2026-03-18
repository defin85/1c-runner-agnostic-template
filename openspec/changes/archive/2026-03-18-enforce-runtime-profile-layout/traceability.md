# Матрица трассируемости

## Requirement -> Code -> Test

| Требование | Код / артефакты | Проверка |
| --- | --- | --- |
| `runtime-profile-schema.canonical-local-runtime-profile-layout` | `.gitignore`, `env/.local/README.md`, `env/README.md`, `README.md`, `scripts/lib/runtime-profile.sh` | `bash tests/smoke/runtime-doctor-contract.sh`, `bash tests/smoke/copier-update-ready.sh`, `openspec validate enforce-runtime-profile-layout --strict --no-interactive` |
| `agent-runtime-toolkit.machine-readable-runtime-artifacts` | `scripts/diag/doctor.sh`, `env/README.md`, `README.md` | `bash tests/smoke/runtime-doctor-contract.sh`, `bash tests/smoke/copier-update-ready.sh` |
