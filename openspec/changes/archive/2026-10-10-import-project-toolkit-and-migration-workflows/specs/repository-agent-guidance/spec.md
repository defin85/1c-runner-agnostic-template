## MODIFIED Requirements

### Requirement: Agent Verification Runbook

The repository SHALL provide a documented, dependency-light verification path for first-pass agent work.

#### Scenario: New agent wants a quick baseline

- **WHEN** an agent needs to verify onboarding assumptions or a documentation/tooling change
- **THEN** the repository MUST provide a documented repo-owned baseline command or target for agent verification
- **AND** that baseline MUST avoid requiring a licensed 1C runtime and the `bsl-analyzer` MCP server used by `make analyze-bsl`
- **AND** the verification runbook MUST explain which deeper contours remain outside the baseline and when to use them
