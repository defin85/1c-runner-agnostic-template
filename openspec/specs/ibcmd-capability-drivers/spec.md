# ibcmd-capability-drivers Specification

## Purpose
TBD - created by archiving change add-ibcmd-capability-drivers. Update Purpose after archive.
## Requirements
### Requirement: Stable Runtime Entrypoints With Internal Driver Selection

The template SHALL preserve stable public entrypoints for the core runtime capabilities while allowing the backend 1C toolchain to vary by internal driver selection.

#### Scenario: Generated project uses default runtime flow

- **WHEN** a generated project calls `scripts/platform/create-ib.sh`, `scripts/platform/dump-src.sh`, `scripts/platform/load-src.sh`, or `scripts/platform/update-db.sh`
- **THEN** the public entrypoint path and capability intent MUST remain stable
- **AND** the runtime toolkit MUST resolve the backend implementation internally rather than through a second public script namespace
- **AND** omission of an explicit driver MUST select `designer`

### Requirement: Per-Capability Driver Selection For Core Runtime Capabilities

The runtime profile SHALL allow `create-ib`, `dump-src`, `load-src`, and `update-db` to choose a driver independently on a per-capability basis.

#### Scenario: Project opts into ibcmd for selected capabilities

- **WHEN** the runtime profile sets the driver of one or more supported capabilities to `ibcmd`
- **THEN** the toolkit MUST dispatch only those capabilities to the `ibcmd` driver
- **AND** other capabilities MUST keep their own configured driver or the default `designer`
- **AND** driver selection for one capability MUST NOT implicitly change unrelated capabilities

### Requirement: Structured Ibcmd Runtime Coordinates

The template SHALL require explicit `ibcmd`-specific runtime coordinates when a capability selects the `ibcmd` driver.

#### Scenario: Capability uses ibcmd in a supported topology

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` selects the `ibcmd` driver
- **THEN** the runtime profile MUST provide a structured `ibcmd` block with:
  - a selected `runtimeMode`
  - a structured server-access block
  - the topology-specific fields required for that mode
- **AND** the runtime profile MUST provide the path to the `ibcmd` executable separately from the default designer executable
- **AND** the documentation MUST explicitly describe which `runtimeMode` and server-access combinations are supported in the current release

### Requirement: Hierarchical Source Tree Contract For Ibcmd

The template SHALL define a canonical source-tree contract that is compatible with the `ibcmd` driver.

#### Scenario: Project exchanges configuration XML through ibcmd

- **WHEN** a capability uses the `ibcmd` driver to export or import configuration XML files
- **THEN** the generated project documentation MUST define the canonical source-tree format as hierarchical
- **AND** the toolkit MUST NOT silently assume compatibility with unsupported XML layout variants

### Requirement: Partial Configuration Import Through Load-Src

The runtime toolkit SHALL support loading a selected subset of configuration files into an infobase when the runtime flow explicitly requests partial import.

#### Scenario: Project applies a selected configuration diff through ibcmd

- **WHEN** `load-src` runs with `driver=ibcmd`
- **AND** the runtime flow passes an explicit selection of configuration files
- **THEN** the toolkit MUST map that request to the `ibcmd` partial import mechanism that corresponds to the selected runtime mode
- **AND** the selected file paths MUST be interpreted relative to the configured source tree
- **AND** the documentation MUST state which `ibcmd.runtimeMode` values support partial import in the current release

### Requirement: Fail-Closed Validation For Unsupported Driver Combinations

The runtime toolkit SHALL reject unsupported or underspecified capability driver combinations before any 1C runtime command starts.

#### Scenario: Ibcmd profile is incomplete for the selected runtime mode

- **WHEN** a capability selects `ibcmd`
- **AND** the runtime profile is missing one or more fields required by the selected `ibcmd.runtimeMode`
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error message MUST identify which mode-specific field is missing or unsupported
- **AND** the toolkit MUST NOT silently fallback to `designer`

#### Scenario: Ibcmd server-access mode is outside the supported matrix

- **WHEN** a capability selects `ibcmd`
- **AND** the runtime profile requests an unsupported server-access mode such as `pid` or `remote`
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error MUST identify the unsupported support-matrix combination explicitly

### Requirement: Machine-Readable Driver Visibility

Runtime capability artifacts SHALL expose which driver executed the capability without leaking secrets.

#### Scenario: Agent inspects ibcmd run result

- **WHEN** `create-ib`, `dump-src`, `load-src`, or `update-db` runs with `driver=ibcmd`
- **THEN** the runtime artifacts MUST include the selected `ibcmd.runtimeMode`
- **AND** the artifacts MUST include only redacted mode-specific diagnostic metadata
- **AND** the artifacts MUST NOT include resolved secret values, DBMS passwords, or secret-bearing connection strings

### Requirement: Explicit Ibcmd Runtime Modes

The runtime toolkit SHALL distinguish between the supported `ibcmd` topologies instead of treating every `ibcmd` execution as one generic phase-1 contour.

#### Scenario: Project chooses ibcmd for a file infobase

- **WHEN** a core capability selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=file-infobase`
- **THEN** the toolkit MUST resolve the capability through the `file-infobase` topology contract
- **AND** the toolkit MUST NOT silently reinterpret that profile as `standalone-server` or `dbms-infobase`

#### Scenario: Project chooses ibcmd for a DBMS-backed infobase

- **WHEN** a core capability selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=dbms-infobase`
- **THEN** the toolkit MUST resolve the capability through the DBMS-backed topology contract
- **AND** the documentation MUST state that this contour is safety-sensitive when the target database normally belongs to a server cluster

### Requirement: Mode-Specific Ibcmd Command Assembly

The runtime toolkit SHALL assemble `ibcmd` argv according to the selected capability intent and the selected `ibcmd.runtimeMode`.

#### Scenario: Create infobase uses mode-appropriate create contract

- **WHEN** `create-ib` uses `driver=ibcmd`
- **THEN** the toolkit MUST assemble only the parameters that are valid for the selected `ibcmd.runtimeMode`
- **AND** the toolkit MUST NOT inject irrelevant infobase-auth flags into `ibcmd infobase create`
- **AND** the toolkit MUST fail closed if the selected mode cannot satisfy the create contract

#### Scenario: Configuration import and export follow ibcmd CLI semantics

- **WHEN** `dump-src` or `load-src` uses `driver=ibcmd`
- **THEN** the toolkit MUST assemble `config export` and `config import` according to the real `ibcmd` CLI contract of the selected mode
- **AND** the toolkit MUST NOT assume that `ibcmd` accepts the same argument layout as Designer batch mode

#### Scenario: Database update is non-interactive

- **WHEN** `update-db` uses `driver=ibcmd`
- **THEN** the toolkit MUST use an explicit non-interactive update policy
- **AND** the toolkit MUST NOT leave the command waiting for interactive confirmation

### Requirement: Explicit Git-Diff Bridge To Partial Load-Src

Runtime toolkit MUST поддерживать repo-owned bridge, который превращает git-backed source diff в explicit selection для partial `load-src`, не меняя существующую import semantics capability `load-src`.

#### Scenario: Wrapper derives a partial import selection from git-backed source changes

- **WHEN** repo-owned diff-aware wrapper вычисляет changed files для `src/cf`
- **THEN** он ДОЛЖЕН передавать в `load-src` только explicit relative file paths внутри configured source tree
- **AND** удалённые или несуществующие paths НЕ ДОЛЖНЫ попадать в `--files`
- **AND** actual partial import semantics ДОЛЖНА оставаться за capability `load-src`

#### Scenario: Diff-aware wrapper stays independent from patch-oriented diff output

- **WHEN** template или generated project использует `scripts/platform/load-diff-src.sh`
- **THEN** wrapper НЕ ДОЛЖЕН парсить patch-output `scripts/platform/diff-src.sh`
- **AND** wrapper НЕ ДОЛЖЕН зависеть от произвольного profile-defined `capabilities.diffSrc.command` как machine-readable source of changed files
- **AND** selection logic ДОЛЖНА оставаться repo-owned и deterministic

### Requirement: Explicit Commit-Scoped Bridge To Partial Load-Src

Runtime toolkit MUST поддерживать repo-owned bridge, который превращает committed task scope в explicit selection для partial `load-src`, не меняя существующую import semantics capability `load-src`.

#### Scenario: Wrapper derives a partial import selection from canonical task markers

- **WHEN** repo-owned task-scoped wrapper вычисляет commit selection по trailer `Bead:` или `Work-Item:`
- **THEN** он ДОЛЖЕН передавать в `load-src` только explicit relative file paths внутри configured source tree
- **AND** удалённые, несуществующие или внешние paths НЕ ДОЛЖНЫ попадать в `--files`
- **AND** actual partial import semantics ДОЛЖНА оставаться за capability `load-src`

#### Scenario: Wrapper supports explicit range fallback without changing load-src semantics

- **WHEN** template или generated project использует `scripts/platform/load-task-src.sh --range <revset>`
- **THEN** wrapper ДОЛЖЕН строить file selection из указанного commit range без собственной runtime import реализации
- **AND** он ДОЛЖЕН делегировать actual partial import в существующий `load-src --files`
- **AND** range fallback НЕ ДОЛЖЕН подменять собой canonical trailer-based contract

#### Scenario: Task-scoped wrapper stays independent from git notes and patch parsing

- **WHEN** template или generated project использует `scripts/platform/load-task-src.sh`
- **THEN** wrapper НЕ ДОЛЖЕН зависеть от `git notes` как canonical metadata source
- **AND** wrapper НЕ ДОЛЖЕН парсить patch-output `scripts/platform/diff-src.sh`
- **AND** selection logic ДОЛЖНА оставаться repo-owned и deterministic

