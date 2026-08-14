# agent-runtime-toolkit Specification

## Purpose
Define the canonical repo-owned runtime entrypoints that agents and operators use to work with a 1C infobase: stable commands, machine-readable run artifacts, an adapter-friendly runtime model, and wrappers that load only the current git diff or a committed task scope.
## Requirements
### Requirement: Canonical Runtime Entrypoints

The template SHALL provide canonical, versioned entrypoint scripts for core runtime operations, and each supported capability SHALL have one Python orchestration implementation shared by generated-project Bash and PowerShell launchers.

#### Scenario: Generated project receives stable runtime entrypoints

- **WHEN** a project is created from the template or receives the runtime overlay
- **THEN** it MUST contain documented repository-local entrypoints for creating an infobase, loading and dumping source, updating DB configuration, running tests, publishing HTTP services, and diagnostics
- **AND** equivalent `.sh` and `.ps1` entrypoints MUST delegate to the same Python command and return its exit code

#### Scenario: Thin launcher contract

- **WHEN** a generated-project launcher has been migrated to the Python runtime
- **THEN** the launcher MUST NOT parse runtime profiles, assemble 1C commands, or interpret capability results independently

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

### Requirement: Repo-Owned Diff-Aware Load Wrapper

Шаблон MUST поставлять repo-owned wrapper для сценария "взять source diff и загрузить только его" без дублирования runtime import logic.

#### Scenario: Generated project invokes diff-aware load wrapper

- **WHEN** generated project или source repo вызывает `scripts/platform/load-diff-src.sh`
- **THEN** wrapper ДОЛЖЕН вычислить explicit selection changed files внутри `src/cf`
- **AND** wrapper ДОЛЖЕН делегировать actual import в существующий `scripts/platform/load-src.sh --files`
- **AND** public intent wrapper-а ДОЛЖЕН оставаться отдельным от full `load-src`

#### Scenario: Wrapper publishes machine-readable execution artifacts

- **WHEN** `scripts/platform/load-diff-src.sh` завершает работу
- **THEN** он ДОЛЖЕН писать собственный `summary.json`
- **AND** summary ДОЛЖЕН явно отражать selected files, ignored files и delegated `load-src` artifact path
- **AND** wrapper ДОЛЖЕН возвращать non-zero exit code на failure

#### Scenario: After filtering there are no eligible source files

- **WHEN** diff не даёт ни одного существующего eligible path внутри `src/cf`
- **THEN** wrapper НЕ ДОЛЖЕН запускать `load-src`
- **AND** wrapper ДОЛЖЕН завершаться fail-closed с диагностикой в `stderr.log` и `summary.json`

### Requirement: Repo-Owned Task-Scoped Load Wrapper

Шаблон MUST поставлять repo-owned wrapper для сценария "взять уже закомиченные изменения задачи и загрузить только их" без дублирования runtime import logic.

#### Scenario: Generated project invokes task-scoped load wrapper

- **WHEN** generated project или source repo вызывает `scripts/platform/load-task-src.sh` c selector-ом `--work-item` или `--range`
- **THEN** wrapper ДОЛЖЕН вычислить explicit selection changed files внутри `src/cf`
- **AND** wrapper ДОЛЖЕН делегировать actual import в существующий `scripts/platform/load-src.sh --files`
- **AND** public intent wrapper-а ДОЛЖЕН оставаться отдельным от worktree-oriented `load-diff-src`

#### Scenario: Wrapper publishes machine-readable selection artifacts

- **WHEN** `scripts/platform/load-task-src.sh` завершает работу
- **THEN** он ДОЛЖЕН писать собственный `summary.json`
- **AND** summary ДОЛЖЕН явно отражать selector mode, selected commits, selected files, ignored или deleted paths и delegated `load-src` artifact path
- **AND** wrapper ДОЛЖЕН возвращать non-zero exit code на failure

#### Scenario: Selector does not resolve an eligible task-scoped import

- **WHEN** selector не находит подходящих commits или после фильтрации не остаётся eligible paths внутри `src/cf`
- **THEN** wrapper НЕ ДОЛЖЕН запускать `load-src`
- **AND** wrapper ДОЛЖЕН завершаться fail-closed с диагностикой в `stderr.log` и `summary.json`
