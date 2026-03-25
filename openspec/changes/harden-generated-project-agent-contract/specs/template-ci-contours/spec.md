## MODIFIED Requirements

### Requirement: Agent-Facing Artifact Freshness

Static CI contour MUST проверять integrity, freshness и semantic truthfulness agent-facing documentation, context и verification guidance.

#### Scenario: Agent-facing artifacts drift

- **WHEN** root agent instructions, agent docs index/runbooks, live automation context, repo-local skill packaging, generated onboarding summaries или generated verification semantics расходятся
- **THEN** static contour ДОЛЖЕН падать до продолжения fixture или runtime contours
- **AND** checks ДОЛЖНЫ выполняться без licensed 1C binaries и secret runtime credentials
- **AND** reported failure ДОЛЖЕН указывать, какой класс artifact-ов stale, inconsistent или semantically misleading

### Requirement: Agent-Facing Ownership Verification

Шаблон MUST предоставлять static или fixture-level checks, которые удерживают generated-project agent-facing artifacts в соответствии с задокументированной ownership model и verification contract.

#### Scenario: Template changes generated-project onboarding or maintenance surface

- **WHEN** меняются template docs, bootstrap hooks, context seeds, export tooling, runtime-profile policy или template-maintenance workflow
- **THEN** релевантные static или fixture contours ДОЛЖНЫ валидировать generated-project ownership boundaries, sanctioned runtime-profile policy и freshness expectations
- **AND** эти checks ДОЛЖНЫ ловить raw placeholder drift в generated-project-seeded agent context
- **AND** эти checks ДОЛЖНЫ ловить false-positive verification paths, например placeholder contours, которые возвращают success
- **AND** любой workflow, рекламируемый как canonical template-maintenance path для generated repositories, ДОЛЖЕН либо успешно проходить в fixture smoke, либо перестать рекламироваться как guaranteed-safe
