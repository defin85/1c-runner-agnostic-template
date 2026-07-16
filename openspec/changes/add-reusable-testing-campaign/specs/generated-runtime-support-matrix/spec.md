## MODIFIED Requirements

### Requirement: Vanessa BDD Warm-Service Matrix Entry
The template SHALL represent the optional Vanessa BDD warm-service contour in generated-project runtime support artifacts and SHALL identify explicit test-tooling preparation without embedding project-specific defaults.

#### Scenario: Generated repository advertises scenario-testing warm runs
- **WHEN** a generated repository receives or refreshes runtime support matrix artifacts from the template
- **THEN** the matrix MUST include a `bdd-warm-service` contour entry
- **AND** the entry MUST classify the contour as `operator-local` or `unsupported`, not `supported`
- **AND** the entry MUST identify `init-test-tooling` and `install-test-tooling` as explicit prerequisites when their outputs are absent
- **AND** the entry MUST point to a project-owned runbook or entrypoint explaining required local Vanessa inputs: Vanessa Automation Single path, warmup feature path, library paths, step definitions, extension scope, and `operatorLocalTargets.vanessaBdd` target binding
- **AND** the entry MUST NOT include applied-project infobase names, extension names, file paths, or business scenario names
- **AND** the entry MUST NOT claim that bootstrap or overlay update automatically materializes source extensions or downloads Vanessa Automation Single

## ADDED Requirements

### Requirement: YAxUnit Runtime Preparation Entry

The generated runtime support matrix SHALL describe YAxUnit and YAxUnit warm RPC as operator-local contours backed by explicit initialization of pinned YAxUnit source and a project-owned tests extension.

#### Scenario: Generated project inspects YAxUnit support

- **WHEN** generated-project runtime support artifacts are rendered or refreshed
- **THEN** the matrix MUST route missing source extensions to `init-test-tooling`
- **AND** it MUST route installed source extensions to the existing `sync-yaxunit-runtime` and YAxUnit entrypoints
- **AND** it MUST distinguish source initialization from synchronization into a selected 1C target
