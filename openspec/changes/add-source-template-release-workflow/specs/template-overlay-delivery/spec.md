## MODIFIED Requirements

### Requirement: Overlay Maintenance Path Is Documented And Verified

The template SHALL ship docs and automated checks that describe and verify overlay release maintenance as the default ongoing update path.

#### Scenario: Agent or maintainer follows the documented maintenance path

- **WHEN** a generated repository uses `make template-check-update` or `make template-update`
- **THEN** the documented behavior, scripts, and smoke tests MUST agree on overlay release semantics
- **AND** generated-project docs MUST no longer describe ongoing `copier update` as the primary maintenance path

### Requirement: Source Template Release Publishing Is Explicit

The template source repository SHALL publish overlay release tags only through an explicit repo-owned release workflow.

#### Scenario: Maintainer publishes a new overlay release tag

- **WHEN** the source repository publishes the next template overlay release
- **THEN** it MUST provide a repo-owned release command that validates a clean worktree, current remote-tracking state, and baseline verification before pushing the tag
- **AND** the release workflow MUST create or publish the overlay tag intentionally rather than as a side effect of an ordinary branch push
- **AND** the source repository MUST document that workflow as the canonical source release path

#### Scenario: Maintainer accidentally tries to push an overlay tag

- **WHEN** a maintainer attempts to push `refs/tags/v*` outside the canonical release workflow
- **THEN** a repo-owned hook guardrail MUST fail closed before the remote push completes
- **AND** the failure message MUST point back to the canonical source release command or runbook
