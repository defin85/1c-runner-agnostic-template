# agent-runtime-toolkit Specification

## Purpose
TBD - created by archiving change add-agent-toolkit-and-ci-contours. Update Purpose after archive.
## Requirements
### Requirement: Canonical Runtime Entrypoints

The template SHALL provide canonical, versioned entrypoint scripts for the core 1C runtime operations that agents and humans use in generated projects.

#### Scenario: Generated project receives stable runtime entrypoints

- **WHEN** a project is created from the template
- **THEN** it MUST contain documented script entrypoints for creating an infobase, loading and dumping source, updating DB configuration, running tests, publishing HTTP services, and diagnostics
- **AND** those entrypoints MUST be callable from repository-local paths under `scripts/`

### Requirement: Machine-Readable Runtime Artifacts

Each runtime capability script SHALL produce machine-readable execution artifacts in addition to human-readable logs.

#### Scenario: Agent consumes runtime result

- **WHEN** an agent runs a capability script
- **THEN** the script MUST return a non-zero exit code on failure
- **AND** the run artifacts MUST include a `summary.json`
- **AND** the run artifacts MUST preserve raw logs needed for diagnosis

#### Scenario: Runtime doctor sees non-canonical env layout

- **WHEN** `doctor` inspects a repository whose root `env/` directory contains local `*.json` profiles outside the canonical allowlist and outside `env/.local/`
- **THEN** `doctor` MUST report that layout drift in a machine-readable warning section of `summary.json`
- **AND** the warning MUST identify the unexpected paths and the recommended sandbox location for ad-hoc profiles
- **AND** `doctor` MUST keep overall status successful if all runtime preconditions are otherwise satisfied

### Requirement: Adapter-Friendly Runtime Model

The runtime toolkit SHALL expose a stable public contract while allowing the underlying 1C execution backend to vary by adapter.

#### Scenario: Same capability runs through different adapters

- **WHEN** a generated project chooses `direct-platform`, `remote-windows`, or another supported adapter
- **THEN** the public entrypoint path and intent of the capability MUST remain stable
- **AND** the adapter-specific logic MUST stay behind the script contract rather than leak into user workflows

#### Scenario: Direct-platform launch needs GUI isolation

- **WHEN** a generated project runs local `1cv8` or `1cv8c` through `runnerAdapter=direct-platform` on WSL/Linux
- **THEN** the stable entrypoint path MUST remain unchanged
- **AND** the adapter MUST be able to apply repo-owned `Xvfb` isolation behind the same script contract when the runtime profile explicitly enables it
- **AND** the same adapter policy MUST apply both to standard-builder capabilities and to profile-defined command arrays whose executable basename is `1cv8` or `1cv8c`
- **AND** generated project workflows MUST NOT require ad-hoc `xvfb-run ./scripts/...` wrappers as the canonical path

#### Scenario: Direct-platform xvfb preconditions are missing

- **WHEN** `platform.xvfb.enabled=true` but required local tools such as `xvfb-run` or `xauth` are unavailable
- **THEN** doctor and runtime execution MUST fail closed before any 1C process starts
- **AND** the reported failure MUST identify the missing wrapper precondition

