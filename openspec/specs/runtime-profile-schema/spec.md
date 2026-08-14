# runtime-profile-schema Specification

## Purpose
Define the schemaVersion 2 runtime profile contract: structured, target-aware profiles with secrets supplied through environment variables, mode-specific ibcmd blocks, sanctioned checked-in profile policy, redacted launcher artifacts and migration of existing generated projects.
## Requirements
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

#### Scenario: Xvfb wrapper is enabled for direct-platform runtime

- **WHEN** a direct-platform capability runs with `platform.xvfb.enabled=true`
- **THEN** the machine-readable artifacts MUST reflect that an `Xvfb` wrapper was selected in a structured adapter-context field shared by capability summaries and doctor diagnostics
- **AND** the artifacts MAY include non-secret `serverArgs` needed for diagnosis
- **AND** the artifacts MUST NOT store unrelated host-specific secret or session data

### Requirement: Canonical Local Runtime Profile Layout

The template SHALL keep the root `env/` layout predictable by reserving root-level runtime profile names for canonical profiles and moving ad-hoc local profiles into a dedicated sandbox directory.

#### Scenario: Generated project receives canonical runtime profile layout

- **WHEN** a project is created from the template or receives a template update
- **THEN** the root `env/` directory MUST reserve runtime profile filenames for:
  - versioned `*.example.json` files;
  - `env/local.json`;
  - `env/wsl.json`;
  - `env/ci.json`;
  - `env/windows-executor.json`
- **AND** the project MUST provide a dedicated local sandbox such as `env/.local/` for ad-hoc or machine-specific runtime profiles
- **AND** the sandbox location MUST be documented and ignored by Git

#### Scenario: Launcher resolves default runtime profile

- **WHEN** a launcher script starts without explicit `--profile`
- **THEN** it MUST keep the existing explicit resolution order
- **AND** it MUST NOT implicitly scan or auto-select profiles from `env/.local/`
- **AND** ad-hoc profile storage under `env/.local/` MUST NOT change the canonical default path `env/local.json`

#### Scenario: Generated project documents shared runtime support

- **WHEN** a generated repository advertises `bdd`, `smoke`, `publishHttp`, or another runtime contour in durable checked-in docs
- **THEN** any contour that depends only on ignored local-private profiles such as `env/local.json` or `env/.local/*.json` MUST be classified as `operator-local` in the checked-in runtime support matrix
- **AND** the repository MUST NOT treat that local-private profile as the sole shared source of truth for baseline-ready contours
- **AND** sanctioned checked-in presets and operator-local contours MUST remain distinguishable in documentation and machine-readable policy

### Requirement: Mode-Specific Ibcmd Profile Blocks

Runtime profiles SHALL encode the selected `ibcmd` topology as an explicit structured mode rather than as an implicit set of loosely related fields.

#### Scenario: Profile uses standalone server topology

- **WHEN** a runtime profile selects `ibcmd.runtimeMode=standalone-server`
- **THEN** the profile MUST provide the structured fields required for the standalone topology
- **AND** the profile MUST NOT rely on file-infobase or DBMS-backed fields to infer the mode implicitly

#### Scenario: Profile uses file infobase topology

- **WHEN** a runtime profile selects `ibcmd.runtimeMode=file-infobase`
- **THEN** the profile MUST provide a structured file-infobase block with the database path
- **AND** the profile MUST keep that topology distinct from the standalone-server block

#### Scenario: Profile uses DBMS-backed topology

- **WHEN** a runtime profile selects `ibcmd.runtimeMode=dbms-infobase`
- **THEN** the profile MUST provide a structured DBMS block with:
  - DBMS kind
  - database server
  - database name
  - DBMS user
  - DBMS password env-var reference
- **AND** the profile MUST keep those fields separate from generic infobase user-password auth

### Requirement: Ibcmd Server-Access Contract

Runtime profiles SHALL represent the way `ibcmd` reaches the target standalone server as an explicit structured block.

#### Scenario: Current release supports local data-dir access

- **WHEN** a runtime profile selects `driver=ibcmd`
- **THEN** the profile MUST describe the `ibcmd` server-access mode explicitly
- **AND** the documentation MUST state that the current release supports only the documented subset of server-access modes
- **AND** unsupported access modes MUST remain invalid until a later change expands the support matrix

### Requirement: Sanctioned Checked-In Runtime Profile Policy

Шаблон MUST давать generated проектам reusable способ различать sanctioned checked-in root-level runtime profiles и ad-hoc или machine-local profiles.

#### Scenario: Generated project keeps only canonical local-private profiles

- **WHEN** generated repository следует default runtime-profile layout из шаблона
- **THEN** root-level names в `env/` ДОЛЖНЫ оставаться зарезервированными под canonical profiles, задокументированные шаблоном
- **AND** ad-hoc или machine-specific profiles ДОЛЖНЫ продолжать жить под `env/.local/` или в эквивалентном документированном local-private sandbox

#### Scenario: Generated project introduces a checked-in team-shared preset

- **WHEN** generated repository осознанно держит дополнительный checked-in root-level runtime profile вне canonical template set
- **THEN** проект ДОЛЖЕН объявить такой preset через явную sanctioned policy, surfaced в repo-owned docs или machine-readable context
- **AND** doctor diagnostics, generated onboarding docs и baseline checks ДОЛЖНЫ одинаково трактовать sanctioned status этого preset-а
- **AND** агент НЕ ДОЛЖЕН выводить легитимность такого preset-а из warning-only поведения

### Requirement: Repo-Owned Launcher Context For Profile-Defined Commands

Шаблон MUST пробрасывать стабильный repo-owned launcher context в `capabilities.<id>.command`, чтобы project-specific contours не переизобретали outer launcher только ради profile metadata и run-root.

#### Scenario: Generated project wires a repo-owned verification entrypoint

- **WHEN** generated repository задаёт `smoke`, `bdd`, `publishHttp` или другой profile-defined `command` через repo-owned entrypoint
- **THEN** launcher ДОЛЖЕН передать entrypoint-у как минимум `ONEC_PROJECT_ROOT`, `ONEC_PROFILE_PATH`, `ONEC_RUNNER_ADAPTER`, `ONEC_CAPABILITY_ID`, `ONEC_CAPABILITY_LABEL` и `ONEC_CAPABILITY_RUN_ROOT`
- **AND** runtime-profile docs ДОЛЖНЫ документировать этот env contract как canonical reusable boundary
- **AND** smoke или fixture checks ДОЛЖНЫ механически подтверждать, что contract реально доезжает до profile-defined command на default launcher path

### Requirement: Target-Aware Runtime Profiles
Runtime profiles SHALL support binding an operator-local profile to an explicit generated-project target configuration when a repository declares multiple target configurations.

#### Scenario: Profile declares its target
- **WHEN** a generated repository declares more than one target under project-owned target metadata
- **THEN** a target-aware runtime profile MUST identify the target it belongs to by stable target id
- **AND** launcher diagnostics MUST expose the selected target id without leaking secrets
- **AND** target-aware commands MUST fail closed when the selected profile target is absent from project-owned target metadata

#### Scenario: Multi-target source commands require target
- **WHEN** a generated repository declares project-owned multi-target metadata
- **THEN** source and extension runtime commands that can affect a target infobase MUST require an explicit target id
- **AND** commands MUST fail closed when the runtime profile target and requested target disagree

### Requirement: Vanessa BDD Target Contract
The template SHALL provide a checked-in target contract for operator-local Vanessa BDD profiles.

#### Scenario: Local BDD profile is selected for warm-service
- **WHEN** a generated repository runs a Vanessa BDD or BDD warm-service entrypoint with a local-private runtime profile
- **THEN** the entrypoint MUST validate the profile against checked-in target truth at `automation/context/operator-local-targets.json` under `operatorLocalTargets.vanessaBdd`
- **AND** the target truth MUST include a stable target id, expected infobase mode, and the non-secret infobase identity fields needed for that mode, such as file path for file infobases or server/ref for client-server infobases
- **AND** the entrypoint MUST fail closed when the local-private profile target id or infobase identity does not match the checked-in target truth
- **AND** local-private profiles MUST remain credential and path carriers rather than the only durable source of target identity
- **AND** the validation contract MUST allow projects to keep BDD unsupported until they explicitly configure their target truth

### Requirement: Repo-Local Port Lease Helper Fallback
The template SHALL provide a repo-local port lease helper fallback for operator-local runtime contours.

#### Scenario: Global port lease helper is not installed
- **WHEN** an operator-local contour needs a TestClient port lease
- **AND** `ONEC_TEST_PORT_LEASE_HELPER` is not set
- **AND** no `onec-test-port-lease` command is available in `PATH`
- **THEN** the contour MUST be able to use a template-managed repo-local helper
- **AND** the helper MUST support at least `lease`, `release`, and `status`
- **AND** the lookup order MUST prefer `ONEC_TEST_PORT_LEASE_HELPER`, then `PATH`, then the template-managed repo-local helper
- **AND** the helper MUST avoid embedding project-specific repository names by default

### Requirement: Direct-Platform Xpra Process Cleanup

The direct-platform adapter SHALL clean up wrapper-owned GUI session processes after an `xpra` runtime command exits.

#### Scenario: Xpra wrapper starts helper processes

- **WHEN** a direct-platform command runs with `platform.xpra.enabled=true`
- **THEN** the wrapper MUST tag the `xpra` session with a per-run token
- **AND** shutdown MUST stop the display and terminate wrapper-owned `xpra`, `Xvfb`, window manager, `dbus`, and `gvfs` helper processes
- **AND** cleanup MUST avoid killing processes that existed before the wrapper started
