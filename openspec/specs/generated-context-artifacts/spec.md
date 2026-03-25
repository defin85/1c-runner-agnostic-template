# generated-context-artifacts Specification

## Purpose
TBD - created by archiving change tighten-generated-project-agent-surface. Update Purpose after archive.
## Requirements
### Requirement: Privacy-Safe Generated Context Artifacts

The template SHALL generate privacy-safe machine-readable context for generated repositories.

#### Scenario: Generated repo refreshes derived context

- **WHEN** `./scripts/llm/export-context.sh --write` runs in a generated repository
- **THEN** `automation/context/source-tree.generated.txt` MUST exclude `local-private` files and machine-local overrides documented by the ownership model
- **AND** the generated artifacts MUST remain stable under `--check` when no repo-owned or template-managed inputs changed

### Requirement: Generated Metadata Captures Critical Identity And Entrypoints

The template SHALL emit actionable generated metadata instead of an almost-empty inventory.

#### Scenario: Generated repo contains a configuration XML

- **WHEN** a generated repository contains `src/cf/Configuration.xml`
- **THEN** `automation/context/metadata-index.generated.json` MUST populate the configuration identity from the XML content
- **AND** the metadata MUST include entrypoint-oriented inventory for at least configuration roots, web or HTTP services when present, scheduled jobs when present, and other high-signal categories that help agents narrow the search space

### Requirement: Semantic Agent Surface Verification

The template SHALL mechanically reject generated-repo agent surface drift that changes onboarding truth, leaks private artifacts, or advertises an impossible closeout path.

#### Scenario: Generated repo drifts to source-centric or leaky guidance

- **WHEN** generated repo docs or derived context route agents to source-repo-centric onboarding, leak `local-private` artifacts, leave critical identity fields empty, or require unconditional `git push` in a repo without a remote
- **THEN** `scripts/qa/check-agent-docs.sh` and the relevant fixture smoke tests MUST fail
- **AND** the reported failure MUST identify which semantic contract drifted
