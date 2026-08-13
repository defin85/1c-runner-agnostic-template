## ADDED Requirements

### Requirement: Structured SchemaVersion 3 Runtime Profiles

The template SHALL define `schemaVersion: 3` profiles with local execution by default, per-capability structured drivers/backends, and an optional structured remote transport.

#### Scenario: Generated project receives canonical schemaVersion 3 examples

- **WHEN** a project is created from the template or receives the runtime overlay
- **THEN** versioned `env/*.example.json` files MUST declare `schemaVersion: 3`
- **AND** local profiles MUST NOT require `runnerAdapter=direct-platform`
- **AND** platform paths, infobase topology, authentication, capability driver/backend, and optional transport MUST remain explicit structured fields

#### Scenario: Unknown combination

- **WHEN** a schemaVersion 3 profile contains an unknown driver, backend, transport, or incompatible platform-only setting
- **THEN** doctor and capability execution MUST fail closed before invoking an external runtime

### Requirement: SchemaVersion 3 Migration Gate

The runtime SHALL accept schemaVersion 3 for the new contract and SHALL provide a deterministic dry-run migration report for schemaVersion 2 profiles during the declared transition.

#### Scenario: Direct-platform schemaVersion 2 profile

- **WHEN** the migration tool receives a schemaVersion 2 profile with `runnerAdapter=direct-platform`
- **THEN** it MUST produce an equivalent local-default schemaVersion 3 profile or a precise fail-closed diagnostic
- **AND** it MUST NOT rewrite the ignored source profile in dry-run mode

#### Scenario: Arbitrary shell orchestration cannot migrate

- **WHEN** a schemaVersion 2 capability contains shell orchestration that has no supported structured backend
- **THEN** migration MUST stop with the required repo-owned backend named
- **AND** it MUST NOT emit a partially working profile

### Requirement: Atomic And Redacted Runtime Artifacts

Runtime-authored JSON artifacts SHALL be atomically published and diagnostics SHALL not reveal resolved secrets.

#### Scenario: Capability publishes summary

- **WHEN** a capability finishes successfully, fails, times out, or is interrupted
- **THEN** readers MUST observe either the previous complete JSON or the new complete JSON
- **AND** diagnostic argv, summary, stdout, and stderr MUST not contain resolved secrets

#### Scenario: External tool requires a secret-bearing argument

- **WHEN** an external tool contract requires a resolved secret in its actual argv or environment
- **THEN** the runtime MUST pass it only to the child process
- **AND** persisted or displayed argv MUST use a redacted representation

## REMOVED Requirements

### Requirement: Structured SchemaVersion 2 Runtime Profiles

**Reason**: SchemaVersion 3 replaces the mandatory local adapter with local-default execution and separates driver/backend from transport.

**Migration**: Run the repo-owned schemaVersion 2 to 3 migration report and review any unsupported shell orchestration before replacing local-private profiles.

### Requirement: SchemaVersion 2 Only Runtime Gate

**Reason**: The runtime contract advances to schemaVersion 3.

**Migration**: SchemaVersion 2 is accepted only by the transition migration path, not as the target runtime contract.

