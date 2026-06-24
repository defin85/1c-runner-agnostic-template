# Change: Add Vanessa BDD warm-service contour

## Why
Generated 1C repositories already have a generic `bdd` capability, but reusable Vanessa Automation warm runs currently require project-local copying of shell glue and target validation.

Recent applied-project work proved the useful reusable parts: a checked-in BDD target contract, fail-closed warm-service lifecycle, and repo-local port lease helper. The template should seed those parts without importing project-specific scenarios, infobases, or extension names.

## What Changes
- Add an optional `bdd-warm-service` runtime contour to generated-project runtime matrix guidance.
- Add a reusable `operatorLocalTargets.vanessaBdd` target contract for validating local BDD profiles.
- Add template-managed warm-service launcher skeletons that fail closed until a project supplies Vanessa extensions, scenarios, and a Vanessa Automation Single path.
- Add a repo-local port lease helper fallback so generated repositories do not depend on a global `onec-test-port-lease` binary.
- Add fixture contracts that prevent applied-project strings from leaking into generated output.

## Impact
- Affected specs: `generated-runtime-support-matrix`, `runtime-profile-schema`, `template-ci-contours`
- Affected code: runtime matrix templates, BDD scripts, port lease helper, generated-project docs, fixture smoke tests
