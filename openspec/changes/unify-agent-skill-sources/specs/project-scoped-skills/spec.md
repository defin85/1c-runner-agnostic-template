## ADDED Requirements

### Requirement: Single Skill Source For Codex And Claude Code

The repository SHALL keep each project-scoped skill once under `.agents/skills/<name>/` and SHALL provide `.claude/skills/<name>/` only as a byte-identical mirror built by a repo-owned command.

#### Scenario: Maintainer changes a skill

- **WHEN** a skill under `.agents/skills/` is added, changed, or removed
- **THEN** `sync-claude-skills` MUST make `.claude/skills/` contain exactly the same skill directories and files, excluding `README.md` and OpenSpec-managed `openspec-*` skills
- **AND** `check-skill-bindings` MUST fail while the mirror differs and MUST name `sync-claude-skills` as the fix

#### Scenario: Imported pack is regenerated

- **WHEN** `sync-imported-skills` regenerates the imported compatibility pack
- **THEN** it MUST render each imported skill only under `.agents/skills/` and MUST rebuild the Claude Code mirror from it
