## MODIFIED Requirements

### Requirement: Local Working-Area Routing For Generated Repositories

Шаблон MUST поставлять краткий directory-local routing guidance для generated-project work в самых friction-heavy рабочих зонах, не загрязняя deployable `src/cf`.

#### Scenario: Agent enters env, tests, scripts, or the shared source router in a generated repository

- **WHEN** агент открывает `env/`, `tests/`, `scripts/` или `src/` внутри generated repository
- **THEN** локальный `AGENTS.md` ДОЛЖЕН маршрутизировать агента к релевантным truth sources и guardrails для этой области
- **AND** локальный guidance ДОЛЖЕН оставаться router-слоем, а не дублировать весь repository manual
- **AND** routing для основной конфигурации ДОЛЖЕН жить выше deployable `src/cf`, например в `src/AGENTS.md` и shared generated-project docs

## ADDED Requirements

### Requirement: Deployable Main Configuration Root Stays Free Of Routing Docs

Шаблон MUST держать template-managed routing и descriptive docs вне importable `src/cf`.

#### Scenario: New generated repository is bootstrapped

- **WHEN** `copier copy` или equivalent bootstrap path рендерит generated repository
- **THEN** template MUST NOT помещать `AGENTS.md`, `README.md` или аналогичные routing-only markdown artifacts внутрь deployable `src/cf`
- **AND** полезный routing/context для dense main configuration tree ДОЛЖЕН быть доступен через `src/AGENTS.md` и generated-project docs вне `src/cf`
