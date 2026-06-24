## MODIFIED Requirements
### Requirement: Structured SchemaVersion 2 Runtime Profiles
The template SHALL define runtime profiles in `schemaVersion: 2` as structured, machine-validated data rather than as free-form shell command blobs.

#### Scenario: Generated project receives canonical runtime profile examples
- **WHEN** a project is created from the template or receives a template update
- **THEN** the versioned `env/*.example.json` files MUST declare `schemaVersion: 2`
- **AND** the profile MUST store infobase topology, authentication model and platform paths in explicit structured fields
- **AND** the canonical source of truth for infobase connection MUST NOT be an embedded full shell command

#### Scenario: Direct-platform profile enables GUI isolation in WSL or Linux
- **WHEN** a generated project wants repo-owned GUI isolation for local `1cv8` or `1cv8c` launches through `runnerAdapter=direct-platform`
- **THEN** the runtime profile MUST support structured `platform.xvfb` and `platform.xpra` blocks rather than require a raw shell wrapper around launcher scripts
- **AND** `platform.xvfb` MUST include `platform.xvfb.enabled` as a boolean and `platform.xvfb.serverArgs` as an array of strings
- **AND** `platform.xpra` MUST include `platform.xpra.enabled` as a boolean, `platform.xpra.xvfbArgs` as an array of strings when enabled, and `platform.xpra.startChild` as an optional non-empty command string
- **AND** the profile MUST allow GUI isolation to stay disabled by default when both blocks are omitted or explicitly turned off

#### Scenario: Xpra wrapper is enabled for direct-platform runtime
- **WHEN** a direct-platform capability runs with `platform.xpra.enabled=true`
- **THEN** the machine-readable artifacts MUST reflect that an `xpra` wrapper was selected in a structured adapter-context field shared by capability summaries and doctor diagnostics
- **AND** the artifacts MAY include non-secret `xvfbArgs` and `startChild` values needed for diagnosis
- **AND** the artifacts MUST NOT store unrelated host-specific secret or session data

### Requirement: Secret Indirection Through Environment Variables
The template SHALL reference secrets through environment-variable indirection rather than literal secret values inside versioned runtime profiles.

#### Scenario: Password-based authentication is required
- **WHEN** an infobase, DBMS or cluster-admin flow needs a password or equivalent secret
- **THEN** the runtime profile MUST store the env var name that supplies the secret
- **AND** the secret value itself MUST remain outside versioned JSON files
- **AND** runtime scripts MUST resolve the referenced env var only at execution time

#### Scenario: Empty password is intentionally configured
- **WHEN** a runtime profile references a password environment variable that is present but empty
- **THEN** runtime scripts MUST treat the secret reference as configured
- **AND** command assembly MUST omit password arguments only where the underlying 1C command accepts an empty password by omission
- **AND** doctor diagnostics MUST report the env var as set without logging the secret value
