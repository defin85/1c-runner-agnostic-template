## ADDED Requirements

### Requirement: Explicit Ibcmd Runtime Modes

The runtime toolkit SHALL distinguish between the supported `ibcmd` topologies instead of treating every `ibcmd` execution as one generic phase-1 contour.

#### Scenario: Project chooses ibcmd for a file infobase

- **WHEN** a core capability selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=file-infobase`
- **THEN** the toolkit MUST resolve the capability through the `file-infobase` topology contract
- **AND** the toolkit MUST NOT silently reinterpret that profile as `standalone-server` or `dbms-infobase`

#### Scenario: Project chooses ibcmd for a DBMS-backed infobase

- **WHEN** a core capability selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=dbms-infobase`
- **THEN** the toolkit MUST resolve the capability through the DBMS-backed topology contract
- **AND** the documentation MUST state that this contour is safety-sensitive when the target database normally belongs to a server cluster

### Requirement: Mode-Specific Ibcmd Command Assembly

The runtime toolkit SHALL assemble `ibcmd` argv according to the selected capability intent and the selected `ibcmd.runtimeMode`.

#### Scenario: Create infobase uses mode-appropriate create contract

- **WHEN** `create-ib` uses `driver=ibcmd`
- **THEN** the toolkit MUST assemble only the parameters that are valid for the selected `ibcmd.runtimeMode`
- **AND** the toolkit MUST NOT inject irrelevant infobase-auth flags into `ibcmd infobase create`
- **AND** the toolkit MUST fail closed if the selected mode cannot satisfy the create contract

#### Scenario: Configuration import and export follow ibcmd CLI semantics

- **WHEN** `dump-src` or `load-src` uses `driver=ibcmd`
- **THEN** the toolkit MUST assemble `config export` and `config import` according to the real `ibcmd` CLI contract of the selected mode
- **AND** the toolkit MUST NOT assume that `ibcmd` accepts the same argument layout as Designer batch mode

#### Scenario: Database update is non-interactive

- **WHEN** `update-db` uses `driver=ibcmd`
- **THEN** the toolkit MUST use an explicit non-interactive update policy
- **AND** the toolkit MUST NOT leave the command waiting for interactive confirmation

## MODIFIED Requirements

### Requirement: Structured Ibcmd Runtime Coordinates

The template SHALL require explicit `ibcmd`-specific runtime coordinates when a capability selects the `ibcmd` driver.

#### Scenario: Capability uses ibcmd in a supported topology

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` selects the `ibcmd` driver
- **THEN** the runtime profile MUST provide a structured `ibcmd` block with:
  - a selected `runtimeMode`
  - a structured server-access block
  - the topology-specific fields required for that mode
- **AND** the runtime profile MUST provide the path to the `ibcmd` executable separately from the default designer executable
- **AND** the documentation MUST explicitly describe which `runtimeMode` and server-access combinations are supported in the current release

### Requirement: Partial Configuration Import Through Load-Src

The runtime toolkit SHALL support loading a selected subset of configuration files into an infobase when the runtime flow explicitly requests partial import.

#### Scenario: Project applies a selected configuration diff through ibcmd

- **WHEN** `load-src` runs with `driver=ibcmd`
- **AND** the runtime flow passes an explicit selection of configuration files
- **THEN** the toolkit MUST map that request to the `ibcmd` partial import mechanism that corresponds to the selected runtime mode
- **AND** the selected file paths MUST be interpreted relative to the configured source tree
- **AND** the documentation MUST state which `ibcmd.runtimeMode` values support partial import in the current release

### Requirement: Fail-Closed Validation For Unsupported Driver Combinations

The runtime toolkit SHALL reject unsupported or underspecified capability driver combinations before any 1C runtime command starts.

#### Scenario: Ibcmd profile is incomplete for the selected runtime mode

- **WHEN** a capability selects `ibcmd`
- **AND** the runtime profile is missing one or more fields required by the selected `ibcmd.runtimeMode`
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error message MUST identify which mode-specific field is missing or unsupported
- **AND** the toolkit MUST NOT silently fallback to `designer`

#### Scenario: Ibcmd server-access mode is outside the supported matrix

- **WHEN** a capability selects `ibcmd`
- **AND** the runtime profile requests an unsupported server-access mode such as `pid` or `remote`
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error MUST identify the unsupported support-matrix combination explicitly

### Requirement: Machine-Readable Driver Visibility

Runtime capability artifacts SHALL expose which driver executed the capability without leaking secrets.

#### Scenario: Agent inspects ibcmd run result

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` runs with `driver=ibcmd`
- **THEN** the runtime artifacts MUST include the selected `ibcmd.runtimeMode`
- **AND** the artifacts MUST include only redacted mode-specific diagnostic metadata
- **AND** the artifacts MUST NOT include resolved secret values, DBMS passwords, or secret-bearing connection strings
