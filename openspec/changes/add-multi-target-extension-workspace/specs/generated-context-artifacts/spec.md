## ADDED Requirements
### Requirement: Multi-Target Configuration Context
The template SHALL support generated-derived context artifacts for repositories that keep several target configuration source trees.

#### Scenario: Generated repo declares target configuration source trees
- **WHEN** a generated repository contains project-owned target metadata for `src/cf/<target-id>`
- **THEN** `./scripts/llm/export-context.sh --write` MUST include each target id, target source path, and compact configuration identity in generated-derived context
- **AND** the generated artifacts MUST treat `src/cf` as a target container when multi-target metadata is present
- **AND** missing target source paths MUST be reported as stale project-owned context rather than silently ignored

#### Scenario: Generated repo declares extension-to-target matrix
- **WHEN** project-owned target metadata maps extensions to targets
- **THEN** generated-derived context MUST expose a compact matrix of target id to extension names
- **AND** each listed extension MUST resolve to an existing `src/cfe/<extension-name>` directory
- **AND** stale matrix entries MUST be detectable by `--check` or an equivalent verification path
