## ADDED Requirements

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
