## MODIFIED Requirements

### Requirement: Canonical Runtime Entrypoints

The template SHALL provide canonical, versioned entrypoint scripts for core runtime operations, and each supported capability SHALL have one Python orchestration implementation shared by generated-project Bash and PowerShell launchers.

#### Scenario: Generated project receives stable runtime entrypoints

- **WHEN** a project is created from the template or receives the runtime overlay
- **THEN** it MUST contain documented repository-local entrypoints for creating an infobase, loading and dumping source, updating DB configuration, running tests, publishing HTTP services, and diagnostics
- **AND** equivalent `.sh` and `.ps1` entrypoints MUST delegate to the same Python command and return its exit code

#### Scenario: Thin launcher contract

- **WHEN** a generated-project launcher has been migrated to the Python runtime
- **THEN** the launcher MUST NOT parse runtime profiles, assemble 1C commands, or interpret capability results independently

### Requirement: Adapter-Friendly Runtime Model

The runtime toolkit SHALL expose stable capability entrypoints while modeling the selected 1C tool as a driver/backend and remote execution as a transport; local execution SHALL be the default and SHALL NOT require a public `direct-platform` selector.

#### Scenario: Same capability runs through different adapters

- **WHEN** a profile selects `designer` or `ibcmd` for a supported capability
- **THEN** the public entrypoint and result contract MUST remain stable
- **AND** driver-specific command assembly MUST stay behind the Python capability contract

#### Scenario: Capability uses a remote transport

- **WHEN** a profile explicitly selects a supported remote Windows transport
- **THEN** the runtime MUST send a structured capability request and preserve the same result contract
- **AND** transport failure MUST remain distinguishable from capability failure

#### Scenario: Direct-platform launch needs GUI isolation

- **WHEN** local `1cv8` or `1cv8c` runs on WSL/Linux with structured Xvfb, Xpra, or `LD_PRELOAD` settings enabled
- **THEN** the stable entrypoint MUST apply the supported POSIX-only isolation internally
- **AND** the same settings in a Windows profile MUST fail closed before process launch

#### Scenario: Direct-platform xvfb preconditions are missing

- **WHEN** a migrated local POSIX profile enables Xvfb but required tools such as `xvfb-run` or `xauth` are unavailable
- **THEN** doctor and runtime execution MUST fail closed before any 1C process starts
- **AND** diagnostics MUST identify the missing platform prerequisite without requiring a public `direct-platform` selector
