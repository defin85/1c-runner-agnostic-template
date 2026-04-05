## MODIFIED Requirements

### Requirement: Intent-To-Capability Mapping

The skill layer SHALL document how common user intents map to skills and to underlying repository entrypoints for both native and imported packs, and it MUST expose native-versus-compatibility preference early enough for skill discovery.

#### Scenario: Agent chooses between native and imported workflows

- **WHEN** a user asks for a capability that exists both as a native runner-agnostic workflow and as an imported compatibility skill
- **THEN** the repository MUST document both mappings in `.agents/skills/README.md` and `.claude/skills/README.md`
- **AND** the mapping MUST identify the repo-owned entrypoint used by each skill
- **AND** the preferred native workflow MUST be visible in discovery-facing metadata or an equivalent first-pass mapping surface rather than only in long-form body text

## ADDED Requirements

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
