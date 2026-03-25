## ADDED Requirements

### Requirement: Agent-Facing Artifact Freshness

The static CI contour SHALL validate the integrity and freshness of agent-facing documentation, context, and skill bindings.

#### Scenario: Agent-facing artifacts drift

- **WHEN** root agent instructions, the agent docs index/runbooks, live automation context, or repo-local skill packaging drift out of sync
- **THEN** the static contour MUST fail before fixture or runtime contours continue
- **AND** the checks MUST run without licensed 1C binaries or secret runtime credentials
- **AND** the reported failure MUST identify which artifact class is stale or inconsistent
