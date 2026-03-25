## ADDED Requirements

### Requirement: Bootstrap Uses Copier Copy Only

The template SHALL use `copier` only for bootstrap of a new generated repository, not for ongoing wrapper-layer updates.

#### Scenario: New project is created from the template

- **WHEN** a repository is generated from the template
- **THEN** `copier copy` MUST remain the bootstrap mechanism
- **AND** the generated repository MUST receive enough checked-in metadata to apply future wrapper overlay releases without `copier update`

### Requirement: Generated Repositories Track Overlay Version Separately

Generated repositories SHALL track the applied wrapper overlay version in a checked-in artifact separate from `.copier-answers.yml`.

#### Scenario: Overlay release is applied

- **WHEN** a generated repository applies a wrapper overlay release
- **THEN** the repository MUST update a checked-in overlay version artifact that identifies the applied template release
- **AND** `.copier-answers.yml` MUST remain bootstrap provenance rather than the primary source of truth for ongoing updates

### Requirement: Overlay Apply Uses Only Managed Paths

Generated repositories SHALL update wrapper-layer files only through an explicit manifest of template-managed paths.

#### Scenario: Product source tree churn exists in the target repository

- **WHEN** the generated repository has large or fully replaced contents under `src/**`
- **THEN** the wrapper overlay apply/check flow MUST operate only on manifest-declared template-managed paths
- **AND** the cost and behavior of the apply/check flow MUST not depend on reconciling product source tree history through `copier update`

### Requirement: Overlay Apply Preserves Project-Owned Truth

The generated-repo maintenance path SHALL preserve project-owned artifacts while still refreshing generated entry surfaces and managed overlays.

#### Scenario: Generated repository applies a new overlay release

- **WHEN** `template-update` applies a newer wrapper overlay release
- **THEN** `README.md`, `openspec/project.md`, and `automation/context/project-map.md` MUST remain project-owned outside explicit managed blocks
- **AND** the maintenance path MUST refresh the managed README router, `AGENTS.md` overlay, and generated-derived context artifacts

### Requirement: Overlay Maintenance Path Is Documented And Verified

The template SHALL ship docs and automated checks that describe and verify overlay release maintenance as the default ongoing update path.

#### Scenario: Agent or maintainer follows the documented maintenance path

- **WHEN** a generated repository uses `make template-check-update` or `make template-update`
- **THEN** the documented behavior, scripts, and smoke tests MUST agree on overlay release semantics
- **AND** generated-project docs MUST no longer describe ongoing `copier update` as the primary maintenance path
