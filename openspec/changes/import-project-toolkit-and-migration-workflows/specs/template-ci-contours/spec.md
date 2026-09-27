## ADDED Requirements

### Requirement: Статическая типизация Python проверяется по baseline

Лёгкий контур без 1С MUST выполнять `scripts/qa/type-check.sh` (и `.ps1` в Windows) через basedpyright из проектного окружения `uv`. Он MUST сравнивать результат с закреплённым baseline. Новые ошибки типизации MUST приводить к ненулевому коду. Уже учтённые в baseline ошибки MUST NOT блокировать проверку. `requirements-dev.txt` MUST быть производным export из `uv.lock` и MUST проверяться на совпадение с ним.

#### Scenario: Новая ошибка типизации

- **WHEN** изменение добавляет в Python-код шаблона ошибку типа, отсутствующую в baseline
- **THEN** `type-check.sh` возвращает ненулевой код и называет файл и строку

#### Scenario: Устаревший export зависимостей

- **WHEN** `uv.lock` изменён, а `requirements-dev.txt` не перегенерирован
- **THEN** проверка завершается ошибкой с командой перегенерации

### Requirement: Новые инструменты покрыты smoke-проверками без 1С

Лёгкий контур MUST выполнять smoke-проверки контракта наблюдения, маршрутизации проверки BSL, путей навыков, инициализации необязательных модулей, обезличивания модуля площадки и контракта исполнителя КД 2.1 на фикстурах без реальной ИБ. Эти проверки MUST NOT делать выводов о синтаксисе или поведении BSL.

#### Scenario: Запуск лёгкого контура

- **WHEN** запускается `make agent-verify` в исходнике шаблона
- **THEN** выполняются `observation-contract.sh`, `check-bsl-routing.sh`, `skill-bindings-paths.sh`, `optional-module-init.sh`, `customer-site-deidentified.sh`, `kd21-workbench-contract.sh` и `python-type-checking-contract.sh`, и любой их отказ делает общий результат неуспешным
