## ADDED Requirements

### Requirement: Пути репозитория в навыках существуют

Проверка `check-skill-bindings` в `qa.py` MUST находить в каждом `SKILL.md` пакета навыков упоминания путей репозитория (repo script, ссылки на документы, сценарии и тесты). Она MUST завершаться ошибкой, если упомянутый путь отсутствует в рабочем дереве. Пути, которые появляются только после инициализации необязательного модуля, MUST проверяться лишь в проектах, где модуль материализован.

#### Scenario: Навык ссылается на удалённый сценарий

- **WHEN** `SKILL.md` содержит `Repo script: ./scripts/diag/missing.sh`, а файла нет
- **THEN** `check-skill-bindings` возвращает ненулевой код и называет навык и отсутствующий путь

#### Scenario: Навык необязательного модуля в проекте без модуля

- **WHEN** модуль `kd21-migration` не материализован
- **THEN** ссылки его заготовок на `migration/kd21/` не считаются ошибкой

### Requirement: Базовый пакет навыков включает инструментарий разработки и наблюдения

Пакет навыков шаблона MUST включать следующие навыки в `.agents/skills/` и в зеркале `.claude/skills/`, которое строит `sync-claude-skills`, каждый с `Repo script` на существующий сценарий или с явным указанием, что навык только маршрутизирует:

- `1c-observe-run`, `1c-run-client`, `1c-check-bsl`;
- `metadata-use`, `metadata-cli-development`;
- `ordinary-form-workflow`, `prepare-external-artifact`, `cfe-form-workflow`;
- `v8unpack`, `1c-rac-operations`, `1c-linux-crash-diagnostics`, `legacy-customization-port`.

Навыки MUST NOT содержать имена заказчика, серверов и баз проекта-источника.

#### Scenario: Проверка состава пакета

- **WHEN** запускается проверка пакета навыков шаблона
- **THEN** каждый из перечисленных навыков присутствует в обоих каталогах, а его пути проходят `check-skill-bindings`

### Requirement: Импортированные редакторы метаданных заменены CLI `metadata`

Шаблон MUST NOT поставлять импортированные навыки `meta-info`, `meta-compile`, `meta-edit`, `meta-remove`, `meta-validate`, `form-info`, `form-add`, `form-compile`, `form-edit`, `form-remove`, `form-validate` и `cfe-borrow`. Команда `sync-imported-skills` MUST пропускать их при обновлении импортированного пакета. Навык `form-patterns` MUST оставаться в пакете. Изменение метаданных MUST выполняться через CLI `metadata` и навык `metadata-use`.

#### Scenario: Обновление импортированного пакета

- **WHEN** выполняется `sync-imported-skills`, а манифест `cc-1c-skills` содержит `meta-edit`
- **THEN** каталоги `.agents/skills/meta-edit` и `.claude/skills/meta-edit` не создаются

#### Scenario: Обновление созданного проекта

- **WHEN** проект, созданный из прежней версии шаблона, выполняет `make template-update`
- **THEN** выведенные навыки удалены из `.agents/skills` и `.claude/skills`, а `form-patterns` и `metadata-use` присутствуют
