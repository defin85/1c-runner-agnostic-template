## MODIFIED Requirements
### Requirement: Fail-Closed Validation For Unsupported Driver Combinations
The runtime toolkit SHALL reject unsupported or underspecified capability driver combinations before any 1C runtime command starts.

#### Scenario: Ibcmd profile is incomplete for the selected runtime mode
- **WHEN** a capability selects `ibcmd`
- **AND** the runtime profile is missing one or more fields required by the selected `ibcmd.runtimeMode`
- **THEN** the launcher or doctor MUST fail closed before runtime invocation
- **AND** the error message MUST identify which mode-specific field is missing or unsupported
- **AND** the toolkit MUST NOT silently fallback to `designer`

#### Scenario: Ibcmd file infobase has no infobase user
- **WHEN** `dump-src`, `load-src`, or `update-db` selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=file-infobase`
- **AND** neither `ibcmd.auth.user` nor `ibcmd.auth.passwordEnv` is present
- **THEN** validation MUST accept the profile without requiring infobase-auth flags
- **AND** command assembly MUST NOT add infobase-auth arguments

#### Scenario: Ibcmd file infobase has partial infobase auth
- **WHEN** `dump-src`, `load-src`, or `update-db` selects `driver=ibcmd`
- **AND** the runtime profile sets `ibcmd.runtimeMode=file-infobase`
- **AND** exactly one of `ibcmd.auth.user` or `ibcmd.auth.passwordEnv` is present
- **THEN** validation MUST fail closed before runtime invocation
- **AND** the error MUST identify the missing paired field

## ADDED Requirements
### Requirement: Generic Extension Source Contours
The runtime toolkit SHALL provide reusable operator-local entrypoints for loading and validating configuration extensions from `src/cfe/*`.

#### Scenario: Project loads selected extensions
- **WHEN** a generated project runs `scripts/platform/load-cfe.sh`
- **THEN** the script MUST discover extension directories under `src/cfe` or accept explicit repeated `--extension <name>`
- **AND** it MUST write top-level and per-extension run-root artifacts
- **AND** it MUST fail closed on the first failed import, check, or apply step
- **AND** it MUST NOT require any project-specific extension name as a default

#### Scenario: Project validates extension configuration
- **WHEN** a generated project runs `check-cfe-applicability` or `check-cfe-config`
- **THEN** the scripts MUST accept explicit extension selection or use directories under `src/cfe`
- **AND** Designer `/Out` diagnostics MUST be converted to machine-readable artifacts
- **AND** inherited borrowed-form handler diagnostics MAY be classified separately from blocking diagnostics when the base form module contains the handler
