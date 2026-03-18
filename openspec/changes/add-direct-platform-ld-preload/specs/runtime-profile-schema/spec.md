## MODIFIED Requirements

### Requirement: Structured SchemaVersion 2 Runtime Profiles

The template SHALL define runtime profiles in `schemaVersion: 2` as structured, machine-validated data rather than as free-form shell command blobs.

#### Scenario: Generated project receives canonical runtime profile examples

- **WHEN** a project is created from the template or receives a template update
- **THEN** the versioned `env/*.example.json` files MUST declare `schemaVersion: 2`
- **AND** the profile MUST store infobase topology, authentication model and platform paths in explicit structured fields
- **AND** the canonical source of truth for infobase connection MUST NOT be an embedded full shell command

#### Scenario: Direct-platform profile enables linker compatibility contour in WSL or Linux

- **WHEN** a generated project wants repo-owned linker compatibility for local `1cv8` or `1cv8c` launches through `runnerAdapter=direct-platform`
- **THEN** the runtime profile MUST support a structured `platform.ldPreload` block rather than require a raw shell prefix around launcher scripts
- **AND** the block MUST include `platform.ldPreload.enabled` as a boolean and `platform.ldPreload.libraries` as an array of strings
- **AND** each configured library path MUST be absolute
- **AND** the profile MUST allow the contour to stay disabled by default when the block is omitted or explicitly turned off

### Requirement: Redacted Launcher Artifacts

Launcher-authored machine-readable artifacts SHALL avoid storing resolved secret values or fully assembled secret-bearing connection strings.

#### Scenario: Capability script writes summary and diagnostics

- **WHEN** a launcher script writes `summary.json` or other structured diagnostics
- **THEN** those artifacts MUST contain only redacted connection metadata needed for diagnosis
- **AND** the launcher itself MUST NOT log resolved secret values
- **AND** the launcher itself MUST NOT emit a fully assembled secret-bearing connection string into its own summary output

#### Scenario: LD_PRELOAD contour is enabled for direct-platform runtime

- **WHEN** a direct-platform capability runs with `platform.ldPreload.enabled=true`
- **THEN** the machine-readable artifacts MUST reflect the selected linker compatibility contour in a structured adapter-context field shared by capability summaries and doctor diagnostics
- **AND** the artifacts MAY include non-secret absolute library paths needed for diagnosis
- **AND** the artifacts MUST NOT store unrelated host-specific secrets or unrelated environment-variable values
