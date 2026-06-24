## ADDED Requirements

### Requirement: Template-Shipped Operator-Local xUnit Contour For Generated Repositories

Шаблон MUST поставлять generated repositories template-managed xUnit contour для `direct-platform`, а не только placeholder launcher slot.

#### Scenario: New generated project receives reusable xUnit baseline

- **WHEN** `copier copy` или overlay update создаёт generated repository из шаблона
- **THEN** repository MUST include repo-owned xUnit assets как минимум `./scripts/test/run-xunit-direct-platform.sh`, `./scripts/test/build-xunit-epf.sh`, `tests/xunit/smoke.quickstart.json` и generic harness source под `src/epf/`
- **AND** shipped harness MUST be server-side only и MUST NOT depend on managed-form default runtime
- **AND** generated docs MUST route the agent from `./scripts/test/run-xunit.sh` to the shipped contour instead of claiming that xUnit is always project-specific by default

### Requirement: Canonical Local TDD Loop For xUnit

Шаблон MUST давать generated repositories один documented local xUnit loop для быстрых `src/cf`-итераций.

#### Scenario: Developer wants to run xUnit against fresh configuration changes

- **WHEN** operator-local generated repository меняет `src/cf` и хочет проверить эти изменения через xUnit
- **THEN** the repository MUST provide one canonical wrapper or runbooked command path that performs `load-diff-src`, `update-db`, and `run-xunit` in that order on the default path
- **AND** that loop MUST stay fail-closed for unsupported delta shapes such as delete-only or rename-style changes that cannot be safely replayed through the diff bridge
- **AND** docs MUST point to the manual full-sync path instead of silently falling back to a broader reload
