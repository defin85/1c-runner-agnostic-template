# project-scoped-skills Specification

## Purpose
TBD - created by archiving change add-agent-toolkit-and-ci-contours. Update Purpose after archive.
## Requirements
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

### Requirement: Repo-Local Codex Customization

The repository SHALL provide repo-local Codex customization artifacts that help Codex discover repeatable workflows and optional external context without assuming machine-specific tooling.

#### Scenario: Codex opens the repository

- **WHEN** Codex inspects the repo-local customization surface
- **THEN** `.codex/` guidance and `.agents/skills/` MUST describe repeatable workflows and optional external context
- **AND** the default checked-in Codex configuration MUST remain safe on machines that do not have local MCP binaries or host-specific paths
- **AND** Codex customization MUST point back to repo-owned scripts or agent docs instead of duplicating runtime logic inline

### Requirement: Intent Mapping For Diff-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ только текущие source changes".

#### Scenario: Agent looks for a repeatable diff-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ только текущий diff исходников
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates

### Requirement: Intent Mapping For Task-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ уже закомиченные изменения задачи".

#### Scenario: Agent looks for a repeatable task-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ изменения конкретной задачи, уже попавшие в commit history
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН документировать canonical selectors `--bead`, `--work-item` и `--range`
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates

### Requirement: Imported Executable Skill Readiness Contract

The template SHALL provide a canonical readiness contract for executable imported skills.

#### Scenario: Imported executable skill is invoked without required local dependencies

- **WHEN** an agent invokes a python-backed or node-backed imported skill and the required local dependencies are not available
- **THEN** the repo-owned dispatcher MUST fail closed with an actionable message that identifies the missing dependency class or bootstrap requirement
- **AND** that message MUST route to the canonical readiness/bootstrap path for imported skills
- **AND** the public contract MUST NOT rely on raw vendored stack traces as the primary user experience

#### Scenario: Generated repo advertises executable imported skills

- **WHEN** generated-project onboarding or verification surfaces present executable imported skills as template-managed workflows
- **THEN** the repository MUST provide a documented readiness/bootstrap path for representative imported skill runtimes
- **AND** baseline agent verification MUST be able to check that contract without requiring a licensed 1C runtime

### Requirement: Project-Aware Recommended Skill Subset

The template SHALL derive a compact first-hour recommended subset from the full project-scoped skills package for generated repositories.

#### Scenario: Generated repo exposes high-signal 1C footprints

- **WHEN** generated-derived context detects high-signal repository footprints such as extensions, external processors, reports, forms-heavy structures, subsystems, SKD-related objects, or service surfaces
- **THEN** the repository MUST expose a compact recommendation layer that maps those footprints to a small subset of relevant native or imported skills
- **AND** that layer MUST route to concrete skill names or repo-owned entrypoints rather than prose-only advice
- **AND** the full `.agents/skills/README.md` MUST remain the authoritative full catalog and mapping table

### Requirement: Imported Skill Provenance And Regeneration

The template SHALL track provenance and regeneration inputs for imported skill packs.

#### Scenario: Imported pack is refreshed from upstream

- **WHEN** maintainers refresh the `cc-1c-skills` import
- **THEN** the repository MUST record the upstream source, commit pin, and license in a checked-in vendor directory
- **AND** it MUST store a generated manifest that maps imported skills to vendored helpers or native aliases
- **AND** the generated `.agents/skills` and `.claude/skills` facades MUST be reproducible from that vendor source and manifest

