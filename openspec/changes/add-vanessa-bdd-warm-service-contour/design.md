# Design: Vanessa BDD warm-service contour

## Context
The reusable template already provides generic `run-bdd.sh`, direct-platform `xpra`, web-client diagnostic hooks, YAxUnit warm service, and a port lease shell library. Applied Delans work showed that the successful Vanessa warm contour uses `VATestContourVanessaServiceConfig` and a `/TESTMANAGER` session, but the Delans repo also contains business-specific feature files, fixtures, extension defaults, and infobase names.

## Goals
- Seed a reusable warm-service contour boundary for generated repositories.
- Keep target identity in checked-in context, not only ignored local profiles.
- Keep port leasing repo-local by default.
- Fail closed until a project adds its own Vanessa runtime assets and scenario sources.

## Non-Goals
- Do not import Delans BDD scenarios, fixtures, manifests, infobase names, or extension defaults.
- Do not promote `DelansCommon` / `DCBddWarmServiceConfig`.
- Do not make BDD warm-service a shared baseline-ready check.

## Decisions
- Decision: add `bdd-warm-service` as an operator-local contour in generated runtime matrix artifacts.
- Decision: validate local BDD profiles against `operatorLocalTargets.vanessaBdd`.
- Decision: make default warm-service extension scope configurable by profile or arguments, with no Delans defaults.
- Decision: ship repo-local `scripts/tools/onec-test-port-lease` and keep `ONEC_TEST_PORT_LEASE_HELPER` override.

## Risks
- Risk: copying applied-project code may introduce local names.
  Mitigation: add string-audit fixture checks for generated artifacts.
- Risk: warm-service launcher becomes too large for the template.
  Mitigation: keep the first implementation fail-closed and skeleton-based unless a project provides the required Vanessa inputs.
