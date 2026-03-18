# runtime-profile-schema Specification

## Purpose
TBD - created by archiving change migrate-runtime-profiles-to-schema-v2. Update Purpose after archive.
## Requirements
### Requirement: Structured SchemaVersion 2 Runtime Profiles

The template SHALL define runtime profiles in `schemaVersion: 2` as structured, machine-validated data rather than as free-form shell command blobs.

#### Scenario: Generated project receives canonical runtime profile examples

- **WHEN** a project is created from the template or receives a template update
- **THEN** the versioned `env/*.example.json` files MUST declare `schemaVersion: 2`
- **AND** the profile MUST store infobase topology, authentication model and platform paths in explicit structured fields
- **AND** the canonical source of truth for infobase connection MUST NOT be an embedded full shell command

### Requirement: Secret Indirection Through Environment Variables

The template SHALL reference secrets through environment-variable indirection rather than literal secret values inside versioned runtime profiles.

#### Scenario: Password-based authentication is required

- **WHEN** an infobase, DBMS or cluster-admin flow needs a password or equivalent secret
- **THEN** the runtime profile MUST store the env var name that supplies the secret
- **AND** the secret value itself MUST remain outside versioned JSON files
- **AND** runtime scripts MUST resolve the referenced env var only at execution time

### Requirement: SchemaVersion 2 Only Runtime Gate

The runtime toolkit SHALL accept only `schemaVersion: 2` profiles and SHALL reject legacy runtime profile formats with an actionable migration error.

#### Scenario: Existing project still uses schemaVersion 1

- **WHEN** a launcher script or runtime doctor loads a profile with `schemaVersion: 1` or an equivalent legacy `shellEnv`-only structure
- **THEN** the command MUST fail closed before any 1C runtime operation starts
- **AND** the error message MUST point to the migration guide or helper

### Requirement: Migration Support For Existing Generated Projects

The template SHALL provide an explicit migration path for generated projects whose ignored local runtime profiles cannot be rewritten by template update.

#### Scenario: Project updates from a legacy template version

- **WHEN** a generated project updates from a template version that used `schemaVersion: 1`
- **THEN** the updated repository MUST include a migration guide and an assisted migration path such as a helper or skeleton generator
- **AND** the documentation MUST explicitly state that ignored local files like `env/local.json` and `env/ci.json` require manual migration by the project owner

### Requirement: Redacted Launcher Artifacts

Launcher-authored machine-readable artifacts SHALL avoid storing resolved secret values or fully assembled secret-bearing connection strings.

#### Scenario: Capability script writes summary and diagnostics

- **WHEN** a launcher script writes `summary.json` or other structured diagnostics
- **THEN** those artifacts MUST contain only redacted connection metadata needed for diagnosis
- **AND** the launcher itself MUST NOT log resolved secret values
- **AND** the launcher itself MUST NOT emit a fully assembled secret-bearing connection string into its own summary output

