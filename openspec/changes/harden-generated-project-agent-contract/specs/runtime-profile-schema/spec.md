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
