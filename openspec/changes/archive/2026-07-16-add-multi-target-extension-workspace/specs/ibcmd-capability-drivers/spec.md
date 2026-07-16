## ADDED Requirements
### Requirement: Target-Aware Source And Extension Runtime Flow
The runtime toolkit SHALL provide target-aware source and extension workflows for multi-target repositories.

#### Scenario: Wrapper loads target extension set
- **WHEN** a generated project runs a target-aware extension load or check command with `--target <target-id>`
- **THEN** the wrapper MUST resolve the target's extension set from project-owned target metadata
- **AND** it MUST delegate each selected extension to existing CFE load/check behavior using `src/cfe/<extension-name>`
- **AND** it MUST fail closed before runtime invocation if any selected extension directory is missing

#### Scenario: Wrapper loads selected target source tree
- **WHEN** a generated project runs `load-src`, `load-diff-src`, or `load-task-src` in multi-target mode
- **THEN** the command MUST require explicit target selection
- **AND** it MUST resolve the source root to `src/cf/<target-id>`
- **AND** it MUST fail closed rather than importing the `src/cf` container as a configuration
