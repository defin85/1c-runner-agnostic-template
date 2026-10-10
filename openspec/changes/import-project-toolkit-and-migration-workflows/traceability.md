# Traceability

## long-operation-observation

- Адаптер наблюдения на Windows даёт те же события и файлы, что на Linux
- Каждый запуск клиента и Designer наблюдается общим адаптером
  - Code: общий адаптер наблюдения (`scripts/lib/capability.sh`, модуль `runtime_*` для Windows), `scripts/adapters/direct-platform.sh`, обёртки `db-run`, `run-client`, EPF/ERF
  - Tests: `tests/smoke/observation-contract.sh`
- Операция без прикладного прогресса останавливается
  - Code: адаптер наблюдения (порог от обёртки, без порога — только `stageAgeSeconds`)
  - Tests: `tests/smoke/observation-contract.sh`
- Технологический журнал включается только на время точного запуска
  - Code: `scripts/diag/technological-log.sh`
  - Tests: `tests/smoke/observation-contract.sh`
- Навык наблюдения задаёт порядок диагностики
  - Docs: `.agents/skills/1c-observe-run/SKILL.md`
  - Tests: `check-skill-bindings`

## onec-development-toolkit

- Команды управления клиентом 1С действуют только на свой сеанс
- Навык запуска клиента запрещает обход штатной обёртки
- Клиент 1С для визуальной проверки запускается штатной обёрткой
  - Code: `scripts/platform/run-client.sh|.ps1`, `scripts/python/run_client.py`, `.agents/skills/1c-run-client/`
  - Tests: `tests/smoke/run-client-contract.sh`

- Проверка BSL выполняется в точном контуре конфигурации
  - Code: `scripts/platform/check-cf-modules.sh`, `resolve-bsl-analyzer-connections.py`, `scripts/python/external_bsl_check.py`, `.agents/skills/1c-check-bsl/`
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
- Резервирование прогона проверяет лимиты хранилища под блокировкой
- Успешный незакреплённый прогон освобождает временные каталоги
- Долгоживущие артефакты хранятся вне checkout
  - Code: `scripts/python/artifact_storage.py`, `make artifact-storage`
  - Tests: `tests/python/test_artifact_storage.py`

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
- Изменяющие операции серверных обёрток выполняются только для явно разрешённой базы
- Серверные обёртки работают на системном Python площадки
  - Code: серверные обёртки `site-*`
  - Tests: запуск read-only команд на Python 3.7, отказ `Refused`
- VDI-клиент работает в изолированном сеансе Xpra
  - Code: сценарий запуска VDI-клиента, навык `site-vdi-xpra`
  - Tests: тест окружения дочернего процесса
- Регламент восстановления доступа указывает границы применимости метода
- Восстановление доступа к ИБ требует резервной копии и проверки возврата
  - Code: обёртка восстановления (опция модуля, Р2)
  - Tests: отказ `hide` без `backup` на фикстуре

## kd21-migration-rules-workbench

- Модуль КД 2.01 материализуется только явной командой
  - Code: `automation/optional/kd21-migration/`, `make optional-module-init`
  - Tests: `tests/smoke/optional-module-init.sh`
- Повторная сборка правил КД 2.01 даёт тот же выпуск
- Ядро компилятора КД 2.01 не зависит от исполнителя и проектных модулей
- Правила КД 2.01 собираются компилятором без 1С
  - Code: `scripts/migration/kd_xml_compiler/`, `kd-rules-cycle run build-rules`
  - Tests: тест границы ядра и повторяемости сборки, `tests/smoke/kd21-workbench-contract.sh`
- Контур изменяет только расходуемые базы профиля
- Прогон выполняется по стадиям с одноразовым каталогом результата
- Прогон держит блокировку профиля и записывает состояние в каталог результата
- Итог прогона подтверждается машинным результатом и манифестом выпуска
- Прикладные стадии подключаются как расширения сценария
  - Code: `scripts/migration/kd-rules-cycle`
  - Tests: `tests/smoke/kd21-workbench-contract.sh`
- Длительные стадии КД наблюдаются общим адаптером
  - Code: `scripts/migration/kd-rules-cycle`, адаптер наблюдения
  - Tests: `tests/smoke/kd21-workbench-contract.sh`, `tests/smoke/observation-contract.sh`
- Регламент правил задаёт подтверждение алгоритмов и компилятора КД
- Регламент правил задаёт число прогонов и хранение доказательств КД
- Регламент правил задаёт правила написания алгоритмов КД
  - Docs: `docs/agent/kd21-rules-workbench-runbook.md` (заготовка модуля)

## project-scoped-skills

- Пути репозитория в навыках существуют
  - Code: `scripts/python/qa.py` (`check-skill-bindings`)
  - Tests: `tests/smoke/skill-bindings-paths.sh`
- Навык базового пакета указывает сценарий или роль маршрутизатора
- Навыки базового пакета не содержат сведений проекта-источника
- Базовый пакет навыков включает инструментарий разработки и наблюдения
  - Code: `.agents/skills/*`, зеркало `.claude/skills/*` (`make sync-claude-skills`)
  - Tests: `check-skill-bindings`, `make agent-verify`
- Импортированные редакторы метаданных заменены CLI `metadata`
  - Code: `scripts/python/imported_skills.py` (`RETIRED_METADATA_SKILLS`), `template-managed-paths.txt`
  - Tests: `tests/python/test_imported_skills.py`, проверка 8.3

## template-overlay-delivery

- Материализованные необязательные модули остаются project-owned
  - Tests: `tests/smoke/optional-module-init.sh`, `tests/smoke/copier-update-ready.sh`, проверка 8.3
- Правки проекта в template-managed файлах переносятся до его обновления
  - Docs: `inventory.md` этого change
- Проектные цели подключаются через `Makefile.project` и `make.project.ps1`
- `agent-verify` выполняет проектные шаги из `scripts/qa/agent-verify.d/`
- `template-update` переносит проектный блок служебных файлов без изменений
- Пути из `template-update-preserve-paths.txt` имеют приоритет над манифестом overlay
- Проект добавляет свои цели и проверки через точки расширения
  - Code: `Makefile` (`-include Makefile.project`), `make.ps1`, `scripts/qa/agent-verify.sh`, `scripts/python/project_extensions.py`, `template-update-preserve-paths.txt`
  - Tests: `tests/smoke/project-extension-points.sh`, `tests/smoke/copier-update-ready.sh`
- Проверка типов не допускает ослабления общих правил в проекте
- Python-конфигурация созданного проекта создаётся один раз и принадлежит проекту
  - Code: `pyproject.toml`, `uv.lock`, `requirements-dev.txt`, `pyrightconfig.json`, `scripts/qa/pyright-base.json`, `scripts/python/type_checking.py`
  - Tests: `tests/smoke/python-type-checking-contract.sh`, `tests/smoke/copier-update-ready.sh`

## template-ci-contours

- Python-код проходит линтер и форматирование ruff
  - Code: `ruff.toml`, `make verify-python-lint`
  - Tests: `make agent-verify`
- Файл `requirements-dev.txt` совпадает с export из `uv.lock`
- Статическая типизация Python проверяется без baseline
  - Code: `scripts/qa/type-check.sh|.ps1`, `pyrightconfig.json`, `pyproject.toml`, `uv.lock`, `requirements-dev.txt`
  - Tests: `tests/smoke/python-type-checking-contract.sh`
- Новые инструменты покрыты smoke-проверками без 1С
  - Tests: `make agent-verify`
