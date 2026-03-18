# Traceability

## Requirement -> Code -> Test

- `ibcmd runtime modes`
  - Code:
    - `scripts/lib/ibcmd.sh`
    - `scripts/lib/onec.sh`
    - `scripts/diag/doctor.sh`
  - Tests:
    - `tests/smoke/runtime-ibcmd-validation-contract.sh`
    - `tests/smoke/runtime-ibcmd-capability-contract.sh`
    - `tests/smoke/runtime-ibcmd-doctor-contract.sh`

- `mode-specific profile schema`
  - Code:
    - `scripts/lib/onec.sh`
    - `scripts/lib/ibcmd.sh`
    - `env/*.example.json`
  - Tests:
    - `tests/smoke/runtime-ibcmd-validation-contract.sh`
    - `tests/smoke/copier-update-ready.sh`

- `correct ibcmd argv assembly`
  - Code:
    - `scripts/lib/ibcmd.sh`
    - `scripts/lib/onec.sh`
  - Tests:
    - `tests/smoke/runtime-ibcmd-capability-contract.sh`

- `redacted mode visibility`
  - Code:
    - `scripts/lib/onec.sh`
    - `scripts/diag/doctor.sh`
  - Tests:
    - `tests/smoke/runtime-ibcmd-capability-contract.sh`
    - `tests/smoke/runtime-ibcmd-doctor-contract.sh`

- `dbms-backed contour documentation`
  - Code:
    - `README.md`
    - `env/README.md`
    - `env/*.example.json`
  - Tests:
    - `tests/smoke/copier-update-ready.sh`
