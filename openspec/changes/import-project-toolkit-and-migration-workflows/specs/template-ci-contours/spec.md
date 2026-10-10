## ADDED Requirements

### Requirement: Python-код проходит линтер и форматирование ruff

Шаблон MUST поставлять `ruff.toml` с правилами `E4`, `E7`, `E9`, `F`, `B`, `I`, `UP`, `target-version = "py312"` и `line-length = 120`. Для серверных обёрток модуля площадки `ruff.toml` MUST задавать `per-file-target-version = "py37"`. Лёгкий контур без 1С MUST выполнять `ruff check` и `ruff format --check` (`make verify-python-lint`, `./make.ps1 verify-python-lint`) и завершаться ненулевым кодом при любом замечании. Каждое подавление `noqa` MUST содержать причину.

#### Scenario: Неиспользуемый импорт

- **WHEN** изменение добавляет в Python-код шаблона неиспользуемый импорт
- **THEN** `make verify-python-lint` возвращает ненулевой код и называет файл, строку и правило `F401`

#### Scenario: Автоисправление не меняет поведение

- **WHEN** на чистом дереве выполняется `ruff check --fix`
- **THEN** рабочее дерево не изменяется

### Requirement: Статическая типизация Python проверяется без baseline

Шаблон MUST поставлять `pyproject.toml` и `uv.lock` с dev-зависимостями ruff и basedpyright. Лёгкий контур без 1С MUST выполнять `scripts/qa/type-check.sh` (и `.ps1` в Windows) через basedpyright из проектного окружения `uv`. basedpyright MUST работать в режиме `standard`. Любая ошибка типизации MUST приводить к ненулевому коду. Шаблон MUST NOT поставлять baseline принятых ошибок; если файл baseline присутствует, проверка MUST завершаться ошибкой.

#### Scenario: Новая ошибка типизации

- **WHEN** изменение добавляет в Python-код шаблона ошибку типа
- **THEN** `type-check.sh` возвращает ненулевой код и называет файл и строку

#### Scenario: Появился файл baseline

- **WHEN** в дереве шаблона присутствует файл baseline принятых ошибок типизации
- **THEN** проверка типизации завершается ошибкой

### Requirement: Файл `requirements-dev.txt` совпадает с export из `uv.lock`

`requirements-dev.txt` MUST быть производным export из `uv.lock` и MUST проверяться на совпадение с ним.

#### Scenario: Устаревший export зависимостей

- **WHEN** `uv.lock` изменён, а `requirements-dev.txt` не перегенерирован
- **THEN** проверка завершается ошибкой с командой перегенерации

### Requirement: Новые инструменты покрыты smoke-проверками без 1С

Лёгкий контур MUST выполнять smoke-проверки контракта наблюдения, запуска клиента, маршрутизации проверки BSL, путей навыков, инициализации необязательных модулей, обезличивания модуля площадки и контракта исполнителя КД 2.1 на фикстурах без реальной ИБ. Эти проверки MUST NOT делать выводов о синтаксисе или поведении BSL.

#### Scenario: Запуск лёгкого контура

- **WHEN** запускается `make agent-verify` в исходнике шаблона
- **THEN** выполняются `observation-contract.sh`, `run-client-contract.sh`, `check-bsl-routing.sh`, `skill-bindings-paths.sh`, `optional-module-init.sh`, `customer-site-deidentified.sh`, `kd21-workbench-contract.sh` и `python-type-checking-contract.sh`, и любой их отказ делает общий результат неуспешным
