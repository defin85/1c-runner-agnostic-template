## MODIFIED Requirements

### Requirement: Runtime Support Matrix Drives Generated Onboarding

The runtime support matrix SHALL be the canonical checked-in runtime truth for generated-project onboarding.

#### Scenario: Agent asks what can be run in this repository

- **WHEN** an agent needs to know which runtime contours are baseline-safe, unsupported, operator-local, or provisioned
- **THEN** the generated onboarding router and read-only onboarding command MUST point to the runtime support matrix instead of inferring support only from ignored local profiles
- **AND** each matrix entry MUST include the contour identifier, status, expected profile provenance, and canonical runbook or entrypoint
- **AND** operator-local contours MUST remain visible to the agent without being misrepresented as shared baseline-ready checks
- **AND** operator-local contours SHOULD be able to route through one project-owned operator-local decision runbook rather than forcing manual navigation across multiple runtime docs
- **AND** the template-shipped `xunit` contour MUST be classified as `operator-local` whenever the generated starter surface wires the reusable direct-platform runner but still depends on operator-owned local profile values such as platform paths or ADD root
