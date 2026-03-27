## ADDED Requirements

### Requirement: Runtime Quick Reference Stays Aligned With Matrix

The template SHALL keep a concise runtime quick reference aligned with the project-owned runtime support matrix in generated repositories.

#### Scenario: Generated repo explains runtime status to a new agent

- **WHEN** a generated repository exposes `docs/agent/runtime-quickstart.md`
- **THEN** the quick reference MUST use the same contour identifiers and status vocabulary as `automation/context/runtime-support-matrix.md` and `.json`
- **AND** each quick-reference contour summary MUST point back to the corresponding canonical runbook, entrypoint, or matrix entry
- **AND** the runtime quick reference MUST remain short enough to answer “what can I run here and with what prerequisites?” without requiring the full general-purpose runtime contract first
