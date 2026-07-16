## ADDED Requirements
### Requirement: Target-Aware Runtime Profiles
Runtime profiles SHALL support binding an operator-local profile to an explicit generated-project target configuration when a repository declares multiple target configurations.

#### Scenario: Profile declares its target
- **WHEN** a generated repository declares more than one target under project-owned target metadata
- **THEN** a target-aware runtime profile MUST identify the target it belongs to by stable target id
- **AND** launcher diagnostics MUST expose the selected target id without leaking secrets
- **AND** target-aware commands MUST fail closed when the selected profile target is absent from project-owned target metadata

#### Scenario: Multi-target source commands require target
- **WHEN** a generated repository declares project-owned multi-target metadata
- **THEN** source and extension runtime commands that can affect a target infobase MUST require an explicit target id
- **AND** commands MUST fail closed when the runtime profile target and requested target disagree
