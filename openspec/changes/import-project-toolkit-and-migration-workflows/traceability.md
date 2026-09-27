# Traceability

## long-operation-observation

- Каждый запуск клиента и Designer наблюдается общим адаптером
  - Code: общий адаптер наблюдения, `scripts/adapters/direct-platform.sh`, обёртки `db-run`, EPF/ERF
  - Tests: `tests/smoke/observation-contract.sh`
- Операция без прикладного прогресса останавливается
  - Code: адаптер наблюдения (`runtimeStageTimeoutSeconds`)
  - Tests: `tests/smoke/observation-contract.sh`
- Технологический журнал включается только на время точного запуска
  - Code: `scripts/diag/technological-log.sh`
  - Tests: `tests/smoke/observation-contract.sh`
- Навык наблюдения задаёт порядок диагностики
  - Docs: `.agents/skills/1c-observe-run/SKILL.md`
  - Tests: `check-skill-bindings`

## onec-development-toolkit

- Проверка BSL выполняется в точном контуре конфигурации
  - Code: `scripts/platform/check-cf-modules.sh`, `.agents/skills/1c-check-bsl/`
  - Tests: `tests/smoke/check-bsl-routing.sh`; live — платформенная компиляция в согласованной ИБ
- Отсутствие авторитетной проверки фиксируется явно
  - Tests: `tests/smoke/check-bsl-routing.sh`
- Метаданные меняются через CLI модели объектов
  - Code: `scripts/python/metadata*.py`, навыки `metadata-use`, `metadata-cli-development`
  - Tests: `tests/python/test_metadata*.py`; структура — `metadata verify` / загрузка платформой
- Обычные формы и внешние обработки адаптируются по регламенту
  - Code: `scripts/python/ordinary_form_conversion.py`, `v8unpack_*.py`, навыки
  - Docs: `docs/agent/ordinary-form-conversion-runbook.md`
- Стандарты разработки доступны из локального кеша
  - Code: `scripts/python/v8std.py`, `scripts/tools/v8std-fetch`, `v8std-search`
- Поиск по репозиторию следует единому регламенту
  - Docs: `docs/agent/repository-search-runbook.md`

## customer-site-operations

- Модуль площадки материализуется только явной командой
  - Code: `make optional-module-init`, `automation/optional/customer-site-operations/`
  - Tests: `tests/smoke/optional-module-init.sh`
- Поставляемые материалы площадки обезличены
  - Tests: `tests/smoke/customer-site-deidentified.sh`, ручная проверка 8.4
- Ввод команды в удалённый терминал проверяется до выполнения
  - Code: инструмент ввода команды оператора
  - Tests: тест инструмента на фикстурах
- Передача файла на сервер подтверждается SHA-256 до установки
  - Code: инструмент передачи файла оператора
  - Tests: тест сборки и сверки на фикстурах
- Серверные обёртки работают на системном Python площадки
  - Code: серверные обёртки `site-*`
  - Tests: запуск read-only команд на Python 3.7, отказ `Refused`
- VDI-клиент работает в изолированном сеансе Xpra
  - Code: сценарий запуска VDI-клиента, навык `site-vdi-xpra`
  - Tests: тест окружения дочернего процесса
- Восстановление доступа к ИБ требует резервной копии и проверки возврата
  - Code: обёртка восстановления (опция модуля, Р2)
  - Tests: отказ `hide` без `backup` на фикстуре

## kd21-migration-rules-workbench

- Модуль КД 2.1 материализуется только явной командой
  - Code: `automation/optional/kd21-migration/`, `make optional-module-init`
  - Tests: `tests/smoke/optional-module-init.sh`
- Контур изменяет только расходуемые базы профиля
- Прогон выполняется по стадиям с одноразовым каталогом результата
- Итог прогона подтверждается машинным результатом и манифестом выпуска
- Прикладные стадии подключаются как расширения сценария
  - Code: `scripts/migration/kd-rules-cycle`
  - Tests: `tests/smoke/kd21-workbench-contract.sh`
- Длительные стадии КД наблюдаются общим адаптером
  - Code: `scripts/migration/kd-rules-cycle`, адаптер наблюдения
  - Tests: `tests/smoke/kd21-workbench-contract.sh`, `tests/smoke/observation-contract.sh`
- Регламент правил задаёт правила написания и проверки алгоритмов КД
  - Docs: `docs/agent/kd21-rules-workbench-runbook.md` (заготовка модуля)

## project-scoped-skills

- Пути репозитория в навыках существуют
  - Code: `scripts/python/qa.py` (`check-skill-bindings`)
  - Tests: `tests/smoke/skill-bindings-paths.sh`
- Базовый пакет навыков включает инструментарий разработки и наблюдения
  - Code: `.agents/skills/*`, `.claude/skills/*`
  - Tests: `check-skill-bindings`, `make agent-verify`

## template-overlay-delivery

- Материализованные необязательные модули остаются project-owned
  - Tests: `tests/smoke/optional-module-init.sh`, `tests/smoke/copier-update-ready.sh`, проверка 8.3
- Правки проекта в template-managed файлах переносятся до его обновления
  - Docs: `inventory.md` этого change

## template-ci-contours

- Статическая типизация Python проверяется по baseline
  - Code: `scripts/qa/type-check.sh|.ps1`, `pyrightconfig.json`
  - Tests: `tests/smoke/python-type-checking-contract.sh`
- Новые инструменты покрыты smoke-проверками без 1С
  - Tests: `make agent-verify`
