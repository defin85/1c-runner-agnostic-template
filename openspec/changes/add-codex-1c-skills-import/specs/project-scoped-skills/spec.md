## MODIFIED Requirements

### Requirement: Project-Scoped Skills Package

The template SHALL provide project-scoped skills for common agent operations in the template source repository and in generated repositories, including a native runner-agnostic pack and a template-managed imported compatibility pack.

#### Scenario: Repository includes native and imported skill packages

- **WHEN** the template source repo is maintained or a repository is generated from the template
- **THEN** it MUST include a versioned `.agents/skills/` package for supported repeatable workflows
- **AND** it MUST include the existing native runner-agnostic skills plus the full imported `cc-1c-skills` compatibility pack
- **AND** any vendor-specific skill facade such as `.claude/skills/` MUST remain a thin packaging layer over the same repo-owned workflow contract
- **AND** the imported pack MUST be backed by checked-in vendor source and remain updateable through template updates

### Requirement: Skills Wrap Repo-Owned Scripts

Project-scoped skills SHALL act as thin wrappers over repository-owned scripts instead of becoming a second source of runtime logic, including imported skills derived from external upstream packs.

#### Scenario: Imported skill executes through a repo-owned dispatcher

- **WHEN** an agent invokes an imported compatibility skill
- **THEN** the skill MUST point to a repo-owned wrapper or dispatcher under `scripts/`
- **AND** the dispatcher MUST choose the vendored helper or native alias behavior without exposing upstream inline execution snippets as the public contract
- **AND** the generated skill markdown MUST not embed PowerShell or platform CLI implementation details copied from upstream

### Requirement: Intent-To-Capability Mapping

The skill layer SHALL document how common user intents map to skills and to underlying repository entrypoints for both native and imported packs.

#### Scenario: Agent chooses between native and imported workflows

- **WHEN** a user asks for a capability that exists both as a native runner-agnostic workflow and as an imported compatibility skill
- **THEN** the repository MUST document both mappings in `.agents/skills/README.md` and `.claude/skills/README.md`
- **AND** the mapping MUST identify the repo-owned entrypoint used by each skill
- **AND** the documentation MUST mark native runner-agnostic skills as the preferred workflow for template-owned runtime profile paths

## ADDED Requirements

### Requirement: Imported Skill Provenance And Regeneration

The template SHALL track provenance and regeneration inputs for imported skill packs.

#### Scenario: Imported pack is refreshed from upstream

- **WHEN** maintainers refresh the `cc-1c-skills` import
- **THEN** the repository MUST record the upstream source, commit pin, and license in a checked-in vendor directory
- **AND** it MUST store a generated manifest that maps imported skills to vendored helpers or native aliases
- **AND** the generated `.agents/skills` and `.claude/skills` facades MUST be reproducible from that vendor source and manifest
