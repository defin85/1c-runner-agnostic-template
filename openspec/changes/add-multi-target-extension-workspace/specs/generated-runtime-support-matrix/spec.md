## ADDED Requirements
### Requirement: Target-Aware Runtime Support Matrix
The runtime support matrix SHALL represent runtime contours that are valid only for selected target configurations.

#### Scenario: Matrix documents target-specific extension checks
- **WHEN** a generated project documents extension load, applicability, config check, update-db, or YAxUnit contours for a multi-target workspace
- **THEN** the matrix entry MUST identify the target ids to which the contour applies
- **AND** the entry MUST list or reference the extension set selected for each target
- **AND** operator-local target profiles MUST remain distinguishable from shared checked-in target metadata

#### Scenario: Matrix and target metadata drift
- **WHEN** a matrix entry references a target id or extension name that no longer exists in project-owned target metadata
- **THEN** semantic checks MUST fail
- **AND** the failure MUST identify the stale target or extension reference
