## ADDED Requirements

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

### Requirement: Adapter-Friendly Runtime Model

The runtime toolkit SHALL expose a stable public contract while allowing the underlying 1C execution backend to vary by adapter.

#### Scenario: Same capability runs through different adapters

- **WHEN** a generated project chooses `direct-platform`, `remote-windows`, or another supported adapter
- **THEN** the public entrypoint path and intent of the capability MUST remain stable
- **AND** the adapter-specific logic MUST stay behind the script contract rather than leak into user workflows
