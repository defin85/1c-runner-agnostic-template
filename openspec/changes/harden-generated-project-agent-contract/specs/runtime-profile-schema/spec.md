## ADDED Requirements

### Requirement: Sanctioned Checked-In Runtime Profile Policy

Шаблон MUST давать generated проектам reusable способ различать sanctioned checked-in root-level runtime profiles и ad-hoc или machine-local profiles.

#### Scenario: Generated project keeps only canonical local-private profiles

- **WHEN** generated repository следует default runtime-profile layout из шаблона
- **THEN** root-level names в `env/` ДОЛЖНЫ оставаться зарезервированными под canonical profiles, задокументированные шаблоном
- **AND** ad-hoc или machine-specific profiles ДОЛЖНЫ продолжать жить под `env/.local/` или в эквивалентном документированном local-private sandbox

#### Scenario: Generated project introduces a checked-in team-shared preset

- **WHEN** generated repository осознанно держит дополнительный checked-in root-level runtime profile вне canonical template set
- **THEN** проект ДОЛЖЕН объявить такой preset через явную sanctioned policy, surfaced в repo-owned docs или machine-readable context
- **AND** doctor diagnostics, generated onboarding docs и baseline checks ДОЛЖНЫ одинаково трактовать sanctioned status этого preset-а
- **AND** агент НЕ ДОЛЖЕН выводить легитимность такого preset-а из warning-only поведения

### Requirement: Repo-Owned Launcher Context For Profile-Defined Commands

Шаблон MUST пробрасывать стабильный repo-owned launcher context в `capabilities.<id>.command`, чтобы project-specific contours не переизобретали outer launcher только ради profile metadata и run-root.

#### Scenario: Generated project wires a repo-owned verification entrypoint

- **WHEN** generated repository задаёт `smoke`, `xunit`, `bdd`, `publishHttp` или другой profile-defined `command` через repo-owned entrypoint
- **THEN** launcher ДОЛЖЕН передать entrypoint-у как минимум `ONEC_PROJECT_ROOT`, `ONEC_PROFILE_PATH`, `ONEC_RUNNER_ADAPTER`, `ONEC_CAPABILITY_ID`, `ONEC_CAPABILITY_LABEL` и `ONEC_CAPABILITY_RUN_ROOT`
- **AND** runtime-profile docs ДОЛЖНЫ документировать этот env contract как canonical reusable boundary
- **AND** smoke или fixture checks ДОЛЖНЫ механически подтверждать, что contract реально доезжает до profile-defined command на default launcher path
