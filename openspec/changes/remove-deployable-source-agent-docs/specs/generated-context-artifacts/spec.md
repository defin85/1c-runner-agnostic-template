## MODIFIED Requirements

### Requirement: Semantic Agent Surface Verification

The template SHALL mechanically reject generated-repo agent surface drift that changes onboarding truth, leaks private artifacts, advertises an impossible closeout path, or pollutes importable `src/cf` with routing docs.

#### Scenario: Generated repo drifts to source-centric or leaky guidance

- **WHEN** generated repo docs or derived context route agents to source-repo-centric onboarding, leak `local-private` artifacts, leave critical identity fields empty, or require unconditional `git push` in a repo without a remote
- **THEN** `scripts/qa/check-agent-docs.sh` and the relevant fixture smoke tests MUST fail
- **AND** the reported failure MUST identify which semantic contract drifted

#### Scenario: Generated repo contains non-1C markdown artifacts inside deployable main configuration sources

- **WHEN** generated repo contains `src/cf/AGENTS.md`, `src/cf/README.md`, or another non-1C markdown artifact inside the deployable main configuration tree
- **THEN** semantic checks and fixture smoke MUST fail closed before the repo is presented as import-ready
- **AND** the failure MUST identify the forbidden path under `src/cf`
