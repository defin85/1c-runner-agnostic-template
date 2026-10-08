## ADDED Requirements

### Requirement: Материализованные необязательные модули остаются project-owned

Overlay MUST обновлять заготовки `automation/optional/<module>/` и template-managed исполняемый код модулей. Overlay MUST NOT изменять пути, созданные командой `make optional-module-init`: профили, сценарии, регламенты, навыки и серверные обёртки модуля, а также кеши и каталоги прогонов.

#### Scenario: Обновление проекта с материализованным модулем

- **WHEN** проект с инициализированным модулем `customer-site-operations` выполняет `make template-update` на версию с изменённой заготовкой
- **THEN** `automation/optional/customer-site-operations/` обновлена, а `infra/site/` и `docs/infra/site/` побайтно не изменены

#### Scenario: Первичное создание проекта

- **WHEN** проект создаётся `copier copy`
- **THEN** заготовки модулей присутствуют в `automation/optional/`, а каталоги `infra/site/` и `migration/kd21/` отсутствуют

### Requirement: Правки проекта в template-managed файлах переносятся до его обновления

Перед `template-update` проекта, который изменял template-managed файлы, шаблон MUST содержать результат сверки этих файлов и путей, которые проект убрал из своего `template-managed-paths.txt`: для каждого решение `перенести`, `обобщить`, `оставить в проекте`, `уже есть` или `вывести` с причиной и коммит проекта, на котором выполнена сверка. Правки, которые остаются в проекте, MUST переноситься в project-owned точки расширения, а не терять при обновлении.

#### Scenario: Сверка перед обновлением проекта-источника

- **WHEN** в проекте-источнике готовится `template-update` на версию шаблона с этим change
- **THEN** каждый расходящийся template-managed файл и каждый удалённый проектом путь имеет запись в инвентаре сверки change
- **AND** файлы, изменённые в проекте после коммита сверки, сверены повторно

### Requirement: Проект добавляет свои цели и проверки через точки расширения

Шаблон MUST предоставлять project-owned точки расширения, которые `template-update` не создаёт, не перезаписывает и не удаляет:

- `Makefile.project` подключается в конце `Makefile` через `-include`; `make.project.ps1` подключается `make.ps1`, если файл есть. Цель проекта с именем цели шаблона MUST приводить к ошибке `make.ps1`.
- `agent-verify` после базовых проверок MUST выполнять файлы каталога `scripts/qa/agent-verify.d/` по порядку имён: `*.py` на любой ОС, `*.sh` вне Windows, `*.ps1` на Windows. Первый ненулевой код MUST останавливать проверку с именем шага.
- `.gitignore`, `.gitattributes` и `.contextignore` содержат проектный блок между маркерами `# >>> project-owned block` и `# <<< project-owned block`. `template-update` MUST переносить содержимое блока в новую версию файла без изменений, а при повреждённых маркерах MUST останавливаться, не изменяя файл.

Пути из `template-update-preserve-paths.txt` MUST иметь приоритет над манифестом overlay: запись с `/` в конце защищает весь каталог.

#### Scenario: Обновление проекта с заполненными точками расширения

- **WHEN** в проекте заполнены `Makefile.project`, шаг в `scripts/qa/agent-verify.d/` и проектный блок `.gitignore`, и выполняется `template-update`
- **THEN** эти файлы и строки проектного блока совпадают с состоянием до обновления
- **AND** `make <проектная-цель>` выполняется, а `make agent-verify` запускает проектный шаг после базовых проверок

#### Scenario: Повреждён маркер проектного блока

- **WHEN** в `.gitignore` проекта есть открывающий маркер проектного блока без закрывающего и выполняется `template-update`
- **THEN** обновление завершается ошибкой с именем файла, и `.gitignore` не изменён

### Requirement: Python-конфигурация созданного проекта создаётся один раз и принадлежит проекту

`pyproject.toml`, `uv.lock`, `requirements-dev.txt` и `pyrightconfig.json` MUST попадать в созданный проект при `copier copy` и MUST NOT входить в `template-managed-paths.txt`. `template-update` MUST создавать такой файл только при его отсутствии и MUST NOT перезаписывать существующий. Общие правила типизации MUST лежать в template-managed `scripts/qa/pyright-base.json`, а проектный `pyrightconfig.json` MUST подключать его через `extends`. Проверка типов MUST завершаться ошибкой, если `extends` удалён или указывает на другой файл, режим слабее `standard`, правило отключено или понижено, задан `baselineFile`, версия `ruff`, `basedpyright` или `pytest` ниже требуемой либо `requirements-dev.txt` расходится с `uv.lock`.

#### Scenario: Проектная зависимость переживает обновление

- **WHEN** проект добавил зависимость в `pyproject.toml` и `uv.lock` и дополнительный корень в `include` своего `pyrightconfig.json`, затем выполнил `template-update`
- **THEN** зависимость, lock-файл и корень `include` остались без изменений

#### Scenario: Проект ослабил проверку типов

- **WHEN** в проектном `pyrightconfig.json` задан режим `basic` или удалён `extends`
- **THEN** `make verify-types` завершается с ненулевым кодом и называет нарушенное правило
