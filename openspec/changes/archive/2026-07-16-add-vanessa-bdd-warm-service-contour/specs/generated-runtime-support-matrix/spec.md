## MODIFIED Requirements
### Requirement: Project-Owned Runtime Support Matrix
The template SHALL seed a project-owned runtime support matrix for generated repositories.

#### Scenario: Generated repository receives initial agent-facing context
- **WHEN** `copier copy` creates a generated repository or a template update refreshes generated-project scaffolding
- **THEN** the repository MUST include checked-in runtime support matrix artifacts in machine-readable and human-readable form
- **AND** the machine-readable artifact MUST live at `automation/context/runtime-support-matrix.json`
- **AND** the human-readable companion MUST live at `automation/context/runtime-support-matrix.md`
- **AND** the matrix MUST classify each documented runtime contour at least as `supported`, `unsupported`, `operator-local`, or `provisioned`
- **AND** reusable CFE, X11, port lease, web-client diagnostic, YAxUnit, Vanessa BDD warm-service, and golden-baseline contours seeded by the template MUST be represented without project-specific target names
- **AND** the golden-baseline contour MUST be represented as a mandatory project regression baseline that fails closed until the project supplies its comparison hook

## ADDED Requirements
### Requirement: Vanessa BDD Warm-Service Matrix Entry
The template SHALL represent the optional Vanessa BDD warm-service contour in generated-project runtime support artifacts.

#### Scenario: Generated repository advertises scenario-testing warm runs
- **WHEN** a generated repository receives runtime support matrix artifacts from the template
- **THEN** the matrix MUST include a `bdd-warm-service` contour entry
- **AND** the entry MUST classify the contour as `operator-local` or `unsupported`, not `supported`
- **AND** the entry MUST point to a project-owned runbook or entrypoint explaining required local Vanessa inputs: Vanessa Automation Single path, warmup feature path, library paths, step definitions, extension scope, and `operatorLocalTargets.vanessaBdd` target binding
- **AND** the entry MUST NOT include applied-project infobase names, extension names, file paths, or business scenario names
