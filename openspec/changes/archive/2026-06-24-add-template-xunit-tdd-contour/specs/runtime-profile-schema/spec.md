## ADDED Requirements

### Requirement: Direct-Platform xUnit Starter Profile Fields

Шаблон MUST документировать reusable profile shape для shipped direct-platform xUnit contour в generated repositories.

#### Scenario: Generated repo wires the shipped xUnit runner in a checked-in example profile

- **WHEN** a generated repository uses the template-shipped direct-platform xUnit contour in `env/*.example.json`
- **THEN** `capabilities.xunit.command[0]` MUST point to the repo-owned entrypoint `./scripts/test/run-xunit-direct-platform.sh` or an equivalent direct template-managed path
- **AND** the example profile and durable docs MUST document the required helper fields for that contour, including ADD root, harness source dir, and timeout/config overrides when they are part of the shipped runner contract
- **AND** adapters or presets that do not ship a runnable xUnit contour MUST continue to use `unsupportedReason` instead of pretending the contour is baseline-ready
