## MODIFIED Requirements
### Requirement: Project-Owned Runtime Support Matrix
The template SHALL seed a project-owned runtime support matrix for generated repositories.

#### Scenario: Generated repository receives initial agent-facing context
- **WHEN** `copier copy` creates a generated repository or a template update refreshes generated-project scaffolding
- **THEN** the repository MUST include checked-in runtime support matrix artifacts in machine-readable and human-readable form
- **AND** the machine-readable artifact MUST live at `automation/context/runtime-support-matrix.json`
- **AND** the human-readable companion MUST live at `automation/context/runtime-support-matrix.md`
- **AND** the matrix MUST classify each documented runtime contour at least as `supported`, `unsupported`, `operator-local`, or `provisioned`
- **AND** reusable CFE, X11, port lease, web-client diagnostic, YAxUnit, and golden-baseline contours seeded by the template MUST be represented without project-specific target names
- **AND** the golden-baseline contour MUST be represented as a mandatory project regression baseline that fails closed until the project supplies its comparison hook

### Requirement: Runtime Quick Reference Stays Aligned With Matrix
The template SHALL keep a concise runtime quick reference aligned with the project-owned runtime support matrix in generated repositories.

#### Scenario: Generated repo explains runtime status to a new agent
- **WHEN** a generated repository exposes `docs/agent/runtime-quickstart.md`
- **THEN** the quick reference MUST use the same contour identifiers and status vocabulary as `automation/context/runtime-support-matrix.md` and `.json`
- **AND** each quick-reference contour summary MUST point back to the corresponding canonical runbook, entrypoint, or matrix entry
- **AND** the runtime quick reference MUST remain short enough to answer “what can I run here and with what prerequisites?” without requiring the full general-purpose runtime contract first
- **AND** reusable operator-local contours MUST describe their profile or explicit argument prerequisites rather than naming a source-project infobase or publication
