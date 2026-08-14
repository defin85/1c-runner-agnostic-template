## Why

Generated 1С projects inherit a mixed Bash, PowerShell, and Python runtime surface whose equivalent capabilities can diverge and whose POSIX assumptions make native Windows operation fragile. The template already has a Python CLI foundation, so consolidating orchestration there is the lowest-risk path to native Windows parity without maintaining two implementations.

## What Changes

- Make the Python CLI the single implementation of supported repository capabilities; Bash and PowerShell files become thin launchers.
- Replace the mandatory local `direct-platform` adapter selector with local execution by default, while retaining explicit capability drivers/backends and remote transports.
- Introduce a new runtime profile schema and deterministic migration report for existing schema v2 profiles.
- Add cross-platform process, path, service, lock, atomic artifact, redaction, timeout, cancellation, and postcondition contracts.
- Make generated runtime support matrices platform- and evidence-aware.
- Deliver the new runtime through the versioned template overlay and verify that project-owned/local-private data survives update.
- **BREAKING**: migrated profiles no longer require `runnerAdapter=direct-platform`, and arbitrary profile-defined shell orchestration is not accepted as a supported backend.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-runtime-toolkit`: canonical entrypoints share one Python implementation and one observable result contract.
- `runtime-profile-schema`: profiles use local-default execution, structured drivers/backends/transports, strict migration, and redacted diagnostics.
- `ibcmd-capability-drivers`: driver selection becomes independent of a local platform adapter and keeps structured argv behavior on Windows and Linux.
- `generated-runtime-support-matrix`: support status becomes platform-dimensional and evidence-qualified.
- `template-overlay-delivery`: the Python-first runtime and migration surface are delivered without overwriting project-owned or local-private state.

## Impact

- Affects template source and generated-project surface.
- Primary code: `scripts/python/`, public `.sh`/`.ps1` entrypoints, `make.ps1`, profile examples under `env/`, and overlay/bootstrap tooling.
- Generated templates: runtime profile policy, runtime support matrix, quickstart, operator runbook, and onboarding templates.
- Verification: Python cross-platform tests, runtime smoke contracts, copier/update fixtures, and source release checks.
- Python 3.12+ remains the required repository runtime; 1C, Apache, and other external tools remain operator-local prerequisites.
