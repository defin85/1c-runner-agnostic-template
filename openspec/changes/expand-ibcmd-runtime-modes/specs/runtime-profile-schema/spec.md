## MODIFIED Requirements

### Requirement: Structured SchemaVersion 2 Runtime Profiles

The template SHALL define runtime profiles in `schemaVersion: 2` as structured, machine-validated data rather than as free-form shell command blobs.

#### Scenario: Generated project receives canonical runtime profile examples

- **WHEN** a project is created from the template or receives a template update
- **THEN** the versioned `env/*.example.json` files MUST declare `schemaVersion: 2`
- **AND** the profile MUST store infobase topology, authentication model, platform paths and `ibcmd` topology data in explicit structured fields
- **AND** the canonical source of truth for infobase connection MUST NOT be an embedded full shell command

## ADDED Requirements

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
