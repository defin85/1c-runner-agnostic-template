## MODIFIED Requirements

### Requirement: Stable Runtime Entrypoints With Internal Driver Selection

The template SHALL preserve stable public entrypoints for core runtime capabilities while allowing the backend 1C toolchain to vary by structured driver selection independent of the host operating system.

#### Scenario: Generated project uses default runtime flow

- **WHEN** a generated project calls a core `.sh` or `.ps1` runtime entrypoint
- **THEN** the public entrypoint path and capability intent MUST remain stable
- **AND** the runtime toolkit MUST resolve the backend internally rather than through a second public script namespace
- **AND** omission of an explicit driver MUST select `designer`

#### Scenario: Ibcmd runs on Windows or Linux

- **WHEN** a supported capability selects `driver=ibcmd`
- **THEN** the Python runtime MUST assemble structured `ibcmd` argv without requiring `runnerAdapter=direct-platform`
- **AND** equivalent topology fields MUST have equivalent validation semantics on Windows and Linux

### Requirement: Per-Capability Driver Selection For Core Runtime Capabilities

The runtime profile SHALL allow `create-ib`, `dump-src`, `load-src`, and `update-db` to choose a driver independently on a per-capability basis.

#### Scenario: Project opts into ibcmd for selected capabilities

- **WHEN** the runtime profile sets one or more supported capability drivers to `ibcmd`
- **THEN** the toolkit MUST dispatch only those capabilities to `ibcmd`
- **AND** other capabilities MUST retain their configured driver or default `designer`
- **AND** driver selection MUST NOT imply a local or remote transport

