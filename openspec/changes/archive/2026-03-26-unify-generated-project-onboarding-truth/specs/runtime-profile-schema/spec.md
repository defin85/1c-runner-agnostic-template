## MODIFIED Requirements

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

- **WHEN** a generated repository advertises `xunit`, `bdd`, `smoke`, `publishHttp`, or another runtime contour in durable checked-in docs
- **THEN** any contour that depends only on ignored local-private profiles such as `env/local.json` or `env/.local/*.json` MUST be classified as `operator-local` in the checked-in runtime support matrix
- **AND** the repository MUST NOT treat that local-private profile as the sole shared source of truth for baseline-ready contours
- **AND** sanctioned checked-in presets and operator-local contours MUST remain distinguishable in documentation and machine-readable policy
