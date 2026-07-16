# Change: Multi-target extension workspace

## Why
Generated 1C projects sometimes need one agent-friendly workspace for several related extensions that target different vendor configurations. The current template assumes one primary `src/cf` configuration tree, so agents cannot treat several target configuration source dumps as first-class context for shared and target-specific extension work.

## What Changes
- **BREAKING** Redefine `src/cf` for multi-target generated projects as a container of target configuration source trees, for example `src/cf/ut22`, `src/cf/ut26`, and `src/cf/unf`.
- Keep deployable extension sources under `src/cfe/<extension>`.
- Add machine-readable target metadata and an extension-to-target matrix to generated-project context.
- Extend runtime profile and runtime support contracts so launchers can run source, CFE load/check/test, and context flows for a selected target.
- Update existing automation that assumes `src/cf` is one importable configuration source root.

## Impact
- Affected specs: `runtime-profile-schema`, `generated-context-artifacts`, `generated-runtime-support-matrix`, `ibcmd-capability-drivers`
- Affected code: `scripts/platform/*cfe*.sh`, `scripts/test/*`, `scripts/llm/export-context.sh`, `scripts/diag/doctor.sh`, `automation/context/templates/*`, generated-project docs and smoke tests
