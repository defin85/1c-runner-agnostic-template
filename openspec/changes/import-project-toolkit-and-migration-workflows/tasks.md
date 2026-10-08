Состояние проектирования: решения Р1–Р8 приняты (`design.md`). Артефакты актуализированы 2026-10-08 по коммиту проекта-источника `46c814b51`. Следующие шаги — 0.3 и инвентарь 0.2. Реализация не начата.
Порядок выпуска (Р4): сначала этапы 0–3 и 7 для базового набора, затем 4–6.

## 0. Решения и инвентарь

- [x] 0.1 Получить решения по открытым вопросам 1–4 из `proposal.md` и записать их в `design.md` как принятые решения.
- [x] 0.2 Составить `inventory.md` сверки template-managed файлов проекта-источника относительно `v0.3.36`.
  - Объём на 2026-10-08: 181 расходящийся файл и 70 путей, которые проект убрал из своего `template-managed-paths.txt`. В инвентаре записать коммит проекта, на котором выполнена сверка.
  - Для каждого файла записать решение `перенести|обобщить|оставить в проекте|уже есть|вывести` и причину.
  - Проверка: число записей равно числу расходящихся и удалённых путей на зафиксированном коммите; у каждой записи есть решение.
- [x] 0.3 Перенести ветку change на актуальный `origin/main`, где есть `unify-agent-skill-sources` (зеркало `.claude/skills` через `make sync-claude-skills`).
  - Проверка: `git merge-base --is-ancestor origin/main HEAD` успешен, `openspec validate import-project-toolkit-and-migration-workflows --strict` проходит.
- [x] 0.4 Актуализировать proposal, design, specs и tasks по состоянию проекта-источника на 2026-10-08 и записать решения Р5–Р8.

## 1. Наблюдение длительных операций

- [x] 1.1 Перенести общий адаптер наблюдения и навык `1c-observe-run`: `observation.jsonl` schema v1, `progress.txt`, terminal-секция `summary.json`.
  - Источник: `run_observed_command` из `scripts/lib/capability.sh` (Linux) и `observe-command` из `scripts/python/runtime.py` (Windows). Windows-часть разместить в отдельном модуле `runtime_*`.
  - Добавить остановку процессной группы при неизменном прогрессе (Р7): порог передаёт обёртка, без порога остановки нет. Логику взять из `stall_timeout` в `kd_cycle_common.run`.
- [x] 1.2 Перенести `scripts/diag/technological-log.sh` с operation cursor и восстановлением исходного `logcfg.xml`.
- [x] 1.3 Подключить адаптер к `direct-platform.sh`, `db-run`, `run-client`, EPF/ERF build/dump и операциям с временными файловыми ИБ на Linux и Windows.
  - Сделано: адаптер вызывается в `execute_prepared_capability_command` (`runtime.py`), поэтому наблюдаются все capability-запуски через `direct-platform.sh` и `run-client`.
  - Designer в `cfe_runtime.py`, `db-*` и `epf/erf-*` наблюдаются через `execute_profile_operation`; `db-run` передаётся в `run-client`.
  - Проверка на Windows: код кроссплатформенный, но на Windows не запускался; на Windows `run-client` проверяет владельца клиента только по имени образа.
- [x] 1.4 Добавить `tests/smoke/observation-contract.sh`.
  - Проверка на фикстурных процессах: ровно один terminal, `failed` при отсутствии результата, остановка при неизменном прогрессе с заданным порогом, отсутствие остановки без порога, восстановление `logcfg.xml` после ошибки.
- [x] 1.5 Перенести навык `1c-run-client`, `scripts/platform/run-client.sh|.ps1` и `run_client.py` (Р8); добавить `tests/smoke/run-client-contract.sh`.
  - Проверка на фикстуре: пароль заменён на `***` в выводе и файлах запуска, команды `screenshot|key|click|stop` не действуют на чужой `--run-root`, `--idle-timeout` возвращает 125, запуск наблюдается адаптером.

## 2. Проверка BSL и инструментарий разработки

- [x] 2.1 Перенести навык `1c-check-bsl`, `scripts/platform/check-cf-modules.sh`, `resolve-bsl-analyzer-connections.py` и `external_bsl_check.py` с выводом версии платформы и режима совместимости в результат.
  - Не перенесено: MCP-клиент `analyze-bsl` из проектного `qa.py` (в шаблоне `analyze-bsl` остаётся на BSL LS jar) и `check-bsl-analyzer-connections.sh` (настройка debug-server площадки через systemd).
  - Модули лежат в `scripts/python/`: `bsl_check.py`, `check_cf_modules.py`, `external_bsl_check.py`, `bsl_connections.py`; цели `make check-bsl|check-cf-modules|analyze-bsl-external`.
- [x] 2.2 Добавить `tests/smoke/check-bsl-routing.sh`: выбор модулей, маршрутизация в анализатор или платформу, итог `синтаксис: не проверен` при недоступности, без разбора BSL.
- [x] 2.3 Перенести `scripts/python/metadata*.py` с тестами `tests/python/` и навыки `metadata-use`, `metadata-cli-development`.
- [x] 2.4 Перенести `ordinary_form_conversion.py`, `v8unpack_container.py`, `v8unpack_erf_form.py`, `cfe_templates.py`, навыки `ordinary-form-workflow`, `prepare-external-artifact`, `cfe-form-workflow`, `v8unpack` и `docs/agent/ordinary-form-conversion-runbook.md`, обезличив примеры.
  - Ограничение: этапы с 1С (`prepare`, `build`, `build-published`, `live-*`) вызывают `imported-skill epf-dump|epf-build -Profile` и читают `target.id`, которых нет в профиле v3 шаблона. Без 1С работают `analyze`, `convert`, `verify-remediation`. Сделано вместе с Р11: цель берётся из имени профиля, вызов идёт через `ibcmd` профиля.
- [x] 2.5 Перенести `v8std.py`, `scripts/tools/v8std-fetch`, `v8std-search` с кешем в `.artifacts/v8std` / `V8STD_CACHE_ROOT`.
- [x] 2.6 Перенести `docs/agent/repository-search-runbook.md` (с учётом приоритета проектного поискового регламента в блоке `AGENTS.md` из `origin/main`), `docs/agent/bsl-analyzer-workspace-runbook.md`, навыки `1c-rac-operations`, `1c-linux-crash-diagnostics`, `legacy-customization-port`, удалив проектные имена.
- [x] 2.7 Вывести импортированные `meta-*`, `form-*` (кроме `form-patterns`) и `cfe-borrow` (Р6).
  - Перенести `RETIRED_METADATA_SKILLS` в `imported_skills.py` поверх версии из `origin/main`, убрать навыки из `.agents/skills`, зеркала и `template-managed-paths.txt`, добавить запись в release notes.
  - Проверка: `sync-imported-skills` не создаёт выведенные навыки, `check-skill-bindings` проходит, `template-update` удаляет их в копии созданного проекта.
- [x] 2.8 Перенести хранилище артефактов вне checkout (Р13): `scripts/python/artifact_storage.py`, `scripts/artifact-storage` и `tests/test_artifact_storage.py`.
  - Заменить `fcntl` блокировкой через `runtime_lock`, а `os.statvfs` — `shutil.disk_usage` на Windows (лимиты inode только на Linux); добавить `.ps1`-обёртку; убрать проектное имя каталога (`.tn-bp30-sdd-artifacts` → `<repo>-artifacts`).
  - Проверка: тесты лимитов, резерва и удаления временных каталогов проходят на Linux; модуль импортируется и проверяет свободное место на Windows (тест с имитацией платформы или парная проверка).

## 3. Качество репозитория

- [x] 3.1 Добавить в `check-skill-bindings` проверку существования путей из `SKILL.md` с учётом необязательных модулей; добавить `tests/smoke/skill-bindings-paths.sh`.
- [ ] 3.2 Добавить проверку Python-кода ruff и basedpyright (Р9, Р10).
  - ruff: `ruff.toml` (правила `E4,E7,E9,F,B,I,UP`, `py312`, 120, `per-file-target-version = "py37"` для серверных обёрток площадки), цель `make verify-python-lint` / `./make.ps1 verify-python-lint` с `ruff check` и `ruff format --check`; исправить замечания шаблона, каждый `noqa` с причиной.
  - basedpyright: `pyrightconfig.json` в режиме `standard`, `scripts/python/type_checking.py`, `scripts/qa/type-check.sh|.ps1`, цель `make verify-types`; baseline не поставлять, при наличии baseline-файла проверка падает; исправить ошибки шаблона кодом.
  - Обе цели включить в `make agent-verify`; добавить `tests/smoke/python-type-checking-contract.sh`.
  - Создать в шаблоне `pyproject.toml` и `uv.lock` (их нет) с dev-зависимостями ruff и basedpyright, сделать `requirements-dev.txt` производным export.
  - Проверка: `ruff check`, `ruff format --check` и `basedpyright` без ошибок; после `ruff check --fix` unit-тесты проходят и diff пуст; добавленная в фикстуру ошибка типа даёт ненулевой код с файлом и строкой.
  - Добавить запуск pytest в CI и `agent-verify`: тесты `test_metadata_*.py` написаны для pytest, под `unittest discover` они не выполняются.
  - Сделать `uv.lock` обязательным входом отпечатка движка в `metadata.py` (сейчас необязателен, потому что uv в шаблоне ещё нет).
- [x] 3.3 Перенести общие правки template-managed сценариев по решениям `inventory.md`.
  - Для `runtime.py` — сопоставить с модулями `runtime_*`.
  - Включить возможности по Р12 и импортированные `db-*`/`epf/erf-*` через профиль по Р11 (поведение в `imported_skills.py`, vendor-файлы не править); удалить тесты текста BSL, блок `rlm-tools` и `format-bsl` по Р14; перенести коммит `06b9155` (preserve для `tests/golden/run.sh`).
  - Перед началом повторить сверку для файлов проекта, изменённых после коммита инвентаря `099860613`.
  - Проверка: существующие smoke runtime-контура и `copier-update-ready.sh` проходят.
  - Падение `copier-update-ready.sh` на `runtime-doctor-runtime-mode` было регрессией порта doctor на Python (контекст ibcmd пустой); исправлено кодом, smoke проходит.
- [x] 3.4 Добавить project-owned точки расширения для фрагментов `оставить в проекте` из `inventory.md`: `Makefile.project`/`make.project.ps1`, дополнительные шаги `agent-verify`, проектный блок `.gitignore`/`.gitattributes`.
  - Проверка: `template-update` копии проекта с заполненными точками расширения не меняет их, а проектные цели и шаги `agent-verify` выполняются.
- [ ] 3.5 Закрыть остаток сверки, найденный при выполнении 3.3.
  - Перенести обобщённую Python-проверку документации из проектного `scripts/python/agent_docs.py` без проектных проверок; сейчас Python-версия `check-agent-docs` в шаблоне не ловит `missing required markdown link`, поэтому оставлен shell-вариант.
  - Обновить или удалить smoke, построенные на профиле `schemaVersion` 2 и target-matrix: `runtime-ibcmd-doctor-contract.sh`, `runtime-ibcmd-capability-contract.sh`, `manage-cfe-contract.sh`, `configure-cfe-runtime-flags-contract.sh`, `runtime-load-diff-src*`, `runtime-load-task-src*`, `runtime-profile-legacy-rejection`.
  - Убрать устаревшие `--target` и `capabilities.bdd.command` из навыка `1c-run-bdd`.
  - Проверка: перечисленные smoke проходят или удалены вместе с записями манифеста; `check-agent-docs` на Python падает при отсутствующей обязательной ссылке.

## 4. Необязательные модули: механизм

- [ ] 4.1 Добавить `make optional-module-init MODULE=<имя>` и тонкие Bash/PowerShell-обёртки по образцу `init-test-tooling`.
  - Поведение: preflight всех целевых путей, отказ без изменений при существовании, удаление скопированного при ошибке, регистрация путей как project-owned в preserve-контракте.
- [ ] 4.2 Добавить `tests/smoke/optional-module-init.sh`: первая инициализация, повторная, ошибка посередине, отсутствие изменений материализованных путей после `template-update`.

## 5. Модуль площадки заказчика

- [ ] 5.1 Подготовить `automation/optional/customer-site-operations/`.
  - Состав: регламент площадки, шаблоны инвентаря и профилей `*.example.json`, навыки `site-vdi-xpra`, `rdp-bash-payload`.
  - Все файлы переименованы `tnl-*` → `site-*` и обезличены.
- [ ] 5.2 Перенести инструменты оператора: запуск VDI-клиента в Xpra, ввод команды со сверкой, передача файла фрагментами с SHA-256, keepalive; с их тестами на фикстурах.
- [ ] 5.3 Перенести серверные обёртки на стандартной библиотеке: `site-rac` (включая `jobs-on`/`jobs-off`), `site-ibcmd`, golden/архив/DT, создание согласованной копии базы из DT и удаление неудачной копии, техжурнал, офлайн-лицензирование.
  - Добавить проверку запуска read-only команд на Python 3.7 и отказа `Refused` для базы вне профиля.
- [ ] 5.4 Включить отдельной опцией модуля обёртку восстановления доступа через `v8users` (Р2) с порядком `backup → hide → restore → verify` и отказом `hide` без копии.
- [ ] 5.5 Добавить `tests/smoke/customer-site-deidentified.sh`: поиск IPv4, UUID вне списка фикстур и известных проектных идентификаторов в поставляемых путях модуля.

## 6. Модуль правил КД 2.01

- [ ] 6.0 Перенести ядро компилятора `scripts/migration/kd_xml_compiler/` (Р5): модель метаданных, модель правил, сериализатор КД 2.01, порядок регистрации, адаптер XML структуры.
  - Наложение CFE и построение правил из сценариев БП не переносить. Проверить `metadata_catalog.json.gz` на сведения заказчика или заменить его фикстурой.
  - Проверка: тест границы (ядро не импортирует `kd_cycle_*` и проектные модули); две сборки фикстурного сценария дают побайтно одинаковые XML, ZIP и `manifest.json` без времени и путей запуска.
- [ ] 6.1 Реализовать минимальный исполнитель `scripts/migration/kd-rules-cycle`.
  - Стадии `doctor|reset|build|load|run|verify` на двух расходуемых базах; `build` вызывает компилятор; отдельная сборка `run build-rules` со статусом `rules-built`.
  - Блокировка профиля, `state.json` v2, `result.json`, манифест выпуска, `source-before/after.json`.
  - Отказ при изменении входов, узлы-расширения с режимами повтора.
- [ ] 6.2 Связать `reset` с PostgreSQL golden-контуром шаблона; отказывать, если цель совпадает с эталоном или не входит в список расходуемых баз.
- [ ] 6.3 Подключить блокирующие стадии к адаптеру наблюдения с порогом `runtimeStageTimeoutSeconds` профиля; верхний `observation.jsonl` и `progress.txt`.
- [ ] 6.4 Подготовить `automation/optional/kd21-migration/`.
  - Состав: примеры профиля, `technical-workbench` сценария, матрицы и ожидаемого результата, обработка выгрузки структуры `metadata-exporter`, регламент `kd21-rules-workbench-runbook.md`, обобщённый навык `1c-prepare-manual-migration-bases`, заготовка раздела `## Влияние на миграцию`.
- [ ] 6.5 Добавить `tests/smoke/kd21-workbench-contract.sh` на фикстурном исполнителе стадий.
  - Проверки: отказ при совпадении цели с эталоном, `profile is already running`, `inputs changed`, остановка после `failed`, `rules-built` без обращения к базам, `workbench-run-passed`, `same generation`, расхождение хешей с baseline, неготовая зависимость узла.

## 7. Поверхность создаваемого проекта и документация

- [ ] 7.1 Обновить `template-managed-paths.txt`, preserve-контракт, `recommended-skills`, runtime support matrix и generated-project guidance для новых команд и модулей.
- [ ] 7.2 Построить зеркало `.claude/skills/` командой `make sync-claude-skills` и выполнить `make export-context-write`.

## 8. Финальная проверка

- [ ] 8.1 Выполнить `openspec validate import-project-toolkit-and-migration-workflows --strict --no-interactive`.
- [ ] 8.2 Выполнить `make agent-verify` и `tests/smoke/copier-update-ready.sh` в исходнике шаблона.
- [ ] 8.3 Проверить `copier copy` в пустой каталог и `template-update` копии проекта-источника; убедиться, что после обновления материализованные модули и project-owned пути не изменены.
- [ ] 8.4 Проверить вручную список поставляемых путей необязательного модуля площадки на отсутствие сведений заказчика.
