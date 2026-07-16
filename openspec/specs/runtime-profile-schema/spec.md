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
