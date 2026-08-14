## MODIFIED Requirements

### Requirement: Overlay Apply Uses Only Managed Paths
Generated repositories SHALL update wrapper-layer files only through an explicit manifest of template-managed paths. Test-tooling templates, pinned vendor-source, dependency manifests and initializer/installers SHALL be template-managed, while materialized `src/cfe/**`, `analysis/testing/**` state and `.artifacts/testing/**` SHALL remain outside automatic overlay application.

#### Scenario: Product source tree churn exists in the target repository
- **WHEN** the generated repository has large or fully replaced contents under `src/**`
- **THEN** the wrapper overlay apply/check flow MUST operate only on manifest-declared template-managed paths
- **AND** the cost and behavior of the apply/check flow MUST not depend on reconciling product source tree history through `copier update`

#### Scenario: Overlay refreshes reusable testing tooling
- **WHEN** a project has already materialized or adapted test extensions and applies a newer overlay
- **THEN** the overlay MUST refresh only test-tooling templates, pinned vendor-source, manifests, commands and docs
- **AND** it MUST NOT initialize, replace or delete materialized `src/cfe` extensions, campaign state or installed local binaries
