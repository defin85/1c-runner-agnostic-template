## MODIFIED Requirements

### Requirement: Semantic Agent Surface Verification

The template SHALL mechanically reject generated-repo agent surface drift that changes onboarding truth, leaks private artifacts, or advertises an impossible closeout path.

#### Scenario: Generated repo drifts to source-centric or leaky guidance

- **WHEN** generated repo docs or derived context route agents to source-repo-centric onboarding, leak `local-private` artifacts, leave critical identity fields empty, or require unconditional `git push` in a repo without a remote
- **THEN** `scripts/qa/check-agent-docs.sh` and the relevant fixture smoke tests MUST fail
- **AND** the reported failure MUST identify which semantic contract drifted

#### Scenario: Generated repo promotes local-private runtime truth as shared baseline

- **WHEN** durable docs, project map, onboarding output, or smoke contracts present `env/local.json` or another ignored local-private runtime profile as canonical shared truth for a contour
- **THEN** the semantic checks MUST fail unless a checked-in runtime support matrix classifies that contour as `operator-local` and points to the corresponding runbook or entrypoint
- **AND** runtime support matrix freshness and consistency with the generated onboarding router MUST be validated mechanically
