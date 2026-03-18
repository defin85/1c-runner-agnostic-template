# ibcmd-capability-drivers Specification

## Purpose
TBD - created by archiving change add-ibcmd-capability-drivers. Update Purpose after archive.
## Requirements
### Requirement: Stable Runtime Entrypoints With Internal Driver Selection

The template SHALL preserve stable public entrypoints for the core runtime capabilities while allowing the backend 1C toolchain to vary by internal driver selection.

#### Scenario: Generated project uses default runtime flow

- **WHEN** a generated project calls `scripts/platform/create-ib.sh`, `scripts/platform/dump-src.sh`, `scripts/platform/load-src.sh`, or `scripts/platform/update-db.sh`
- **THEN** the public entrypoint path and capability intent MUST remain stable
- **AND** the runtime toolkit MUST resolve the backend implementation internally rather than through a second public script namespace
- **AND** omission of an explicit driver MUST select `designer`

### Requirement: Per-Capability Driver Selection For Core Runtime Capabilities

The runtime profile SHALL allow `create-ib`, `dump-src`, `load-src`, and `update-db` to choose a driver independently on a per-capability basis.

#### Scenario: Project opts into ibcmd for selected capabilities

- **WHEN** the runtime profile sets the driver of one or more supported capabilities to `ibcmd`
- **THEN** the toolkit MUST dispatch only those capabilities to the `ibcmd` driver
- **AND** other capabilities MUST keep their own configured driver or the default `designer`
- **AND** driver selection for one capability MUST NOT implicitly change unrelated capabilities

### Requirement: Structured Ibcmd Runtime Coordinates

The template SHALL require explicit `ibcmd`-specific runtime coordinates when a capability selects the `ibcmd` driver.

#### Scenario: Capability uses ibcmd in phase 1

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` selects the `ibcmd` driver
- **THEN** the runtime profile MUST provide an `ibcmd`-specific structured configuration block
- **AND** the runtime profile MUST provide the path to the `ibcmd` executable separately from the default designer executable
- **AND** the phase-1 contract MUST explicitly document which `ibcmd` connection mode and transport adapter combinations are supported

### Requirement: Hierarchical Source Tree Contract For Ibcmd

The template SHALL define a canonical source-tree contract that is compatible with the `ibcmd` driver.

#### Scenario: Project exchanges configuration XML through ibcmd

- **WHEN** a capability uses the `ibcmd` driver to export or import configuration XML files
- **THEN** the generated project documentation MUST define the canonical source-tree format as hierarchical
- **AND** the toolkit MUST NOT silently assume compatibility with unsupported XML layout variants

### Requirement: Partial Configuration Import Through Load-Src

The runtime toolkit SHALL support loading a selected subset of configuration files into an infobase when the runtime flow explicitly requests partial import.

#### Scenario: Project applies a selected configuration diff

- **WHEN** `load-src` runs with an explicit selection of configuration files for partial import
- **THEN** the toolkit MUST map that request to the driver-specific partial import mechanism
- **AND** the selected file paths MUST be interpreted relative to the configured source tree
- **AND** the phase-1 documentation MUST state which drivers support partial import in the current release

### Requirement: Fail-Closed Validation For Unsupported Driver Combinations

The runtime toolkit SHALL reject unsupported or underspecified capability driver combinations before any 1C runtime command starts.

#### Scenario: Ibcmd profile is incomplete or incompatible

- **WHEN** a capability selects `ibcmd` but the runtime profile is missing required `ibcmd` fields or violates the documented support matrix
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error message MUST identify which driver/profile precondition is missing or unsupported
- **AND** the toolkit MUST NOT silently fallback to `designer`

### Requirement: Machine-Readable Driver Visibility

Runtime capability artifacts SHALL expose which driver executed the capability without leaking secrets.

#### Scenario: Agent inspects runtime run result

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` writes `summary.json`
- **THEN** the summary MUST include the selected driver
- **AND** the summary MUST contain only redacted metadata needed for diagnostics
- **AND** the summary MUST NOT include resolved secret values or secret-bearing connection strings

