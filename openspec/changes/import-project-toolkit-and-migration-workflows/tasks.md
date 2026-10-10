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
  - Не перенесено в этой задаче: MCP-клиент `analyze-bsl` из проектного `qa.py` (перенесён задачей 3.11) и `check-bsl-analyzer-connections.sh` (настройка debug-server площадки через systemd).
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
- [x] 3.2 Добавить проверку Python-кода ruff и basedpyright (Р9, Р10).
  - ruff: `ruff.toml` (правила `E4,E7,E9,F,B,I,UP`, `py312`, 120, `per-file-target-version = "py37"` для серверных обёрток площадки), цель `make verify-python-lint` / `./make.ps1 verify-python-lint` с `ruff check` и `ruff format --check`; исправить замечания шаблона, каждый `noqa` с причиной.
  - basedpyright: `pyrightconfig.json` в режиме `standard`, `scripts/python/type_checking.py`, `scripts/qa/type-check.sh|.ps1`, цель `make verify-types`; baseline не поставлять, при наличии baseline-файла проверка падает; исправить ошибки шаблона кодом.
  - Обе цели включить в `make agent-verify`; добавить `tests/smoke/python-type-checking-contract.sh`.
  - Создать в шаблоне `pyproject.toml` и `uv.lock` (их нет) с dev-зависимостями ruff и basedpyright, сделать `requirements-dev.txt` производным export.
  - Проверка: `ruff check`, `ruff format --check` и `basedpyright` без ошибок; после `ruff check --fix` unit-тесты проходят и diff пуст; добавленная в фикстуру ошибка типа даёт ненулевой код с файлом и строкой.
  - Добавить запуск pytest в CI и `agent-verify`: тесты `test_metadata_*.py` написаны для pytest, под `unittest discover` они не выполняются.
  - Сделать `uv.lock` обязательным входом отпечатка движка в `metadata.py` (сейчас необязателен, потому что uv в шаблоне ещё нет).
  - Сделано по Р15: `pyproject.toml`, `uv.lock`, `requirements-dev.txt`, `pyrightconfig.json` создаются один раз и принадлежат проекту; общие правила в `scripts/qa/pyright-base.json`. В `agent-verify` идёт быстрый pytest без шести медленных наборов metadata, полный — в CI и `make verify-python-tests`.
  - Не проверено: PowerShell-обёртки и Windows-джобы CI (на машине нет `pwsh`); проверить первым прогоном CI.
- [x] 3.3 Перенести общие правки template-managed сценариев по решениям `inventory.md`.
  - Для `runtime.py` — сопоставить с модулями `runtime_*`.
  - Включить возможности по Р12 и импортированные `db-*`/`epf/erf-*` через профиль по Р11 (поведение в `imported_skills.py`, vendor-файлы не править); удалить тесты текста BSL, блок `rlm-tools` и `format-bsl` по Р14; перенести коммит `06b9155` (preserve для `tests/golden/run.sh`).
  - Перед началом повторить сверку для файлов проекта, изменённых после коммита инвентаря `099860613`.
  - Проверка: существующие smoke runtime-контура и `copier-update-ready.sh` проходят.
  - Падение `copier-update-ready.sh` на `runtime-doctor-runtime-mode` было регрессией порта doctor на Python (контекст ibcmd пустой); исправлено кодом, smoke проходит.
- [x] 3.4 Добавить project-owned точки расширения для фрагментов `оставить в проекте` из `inventory.md`: `Makefile.project`/`make.project.ps1`, дополнительные шаги `agent-verify`, проектный блок `.gitignore`/`.gitattributes`.
  - Проверка: `template-update` копии проекта с заполненными точками расширения не меняет их, а проектные цели и шаги `agent-verify` выполняются.
- [x] 3.5 Закрыть остаток сверки, найденный при выполнении 3.3.
  - Перенести обобщённую Python-проверку документации из проектного `scripts/python/agent_docs.py` без проектных проверок; сейчас Python-версия `check-agent-docs` в шаблоне не ловит `missing required markdown link`, поэтому оставлен shell-вариант.
  - Обновить или удалить smoke, построенные на профиле `schemaVersion` 2 и target-matrix: `runtime-ibcmd-doctor-contract.sh`, `runtime-ibcmd-capability-contract.sh`, `manage-cfe-contract.sh`, `configure-cfe-runtime-flags-contract.sh`, `runtime-load-diff-src*`, `runtime-load-task-src*`, `runtime-profile-legacy-rejection`.
  - Убрать устаревшие `--target` и `capabilities.bdd.command` из навыка `1c-run-bdd`.
  - Проверка: перечисленные smoke проходят или удалены вместе с записями манифеста; `check-agent-docs` на Python падает при отсутствующей обязательной ссылке.
- [x] 3.6 Перевести оставшиеся контуры на профиль v3 и вернуть проверки, отключённые при задаче 3.5.
  - Перевести `scripts/lib/runtime-profile.sh` (тёплый BDD-контур `run-bdd-warm-service.sh`, `run-bdd-warm-run.sh`) на `schemaVersion` 3, чтобы он работал с тем же `env/local.json`, что остальные команды; перевести фикстуру `vanessa-bdd-warm-service-contract.sh` на v3.
  - Перевести `tests/smoke/load-cfe-contract.sh` на профиль v3.
  - Решить, входят ли в контракт `load-diff-src`/`load-task-src` сообщение о пустой выборке в stderr и `summary.json` при ошибке профиля или аргументов (shell-версия их писала, Python-runtime — нет); при положительном решении вернуть поведение в runtime и проверки в smoke.
    - Решение: входят. Спецификация `agent-runtime-toolkit` требует писать `summary.json` при любом завершении обёртки и диагностику в `stderr.log` при пустой выборке. Python-runtime возвращается к поведению shell-версии: при пустой выборке печатает `error: …` в stderr и `stderr.log`; при ошибке профиля или аргументов (кроме `--help`) пишет `summary.json` со `status: failed`.
  - Вернуть `validate_runtime_support_matrix` в проверку документации, когда matrix созданного проекта на Linux и Windows строится одним кодом (см. 7.1); выровнять пересоздание matrix и quickstart при `template-update` на Windows с Linux (сейчас Windows пересоздаёт project-owned файлы при каждом обновлении).
  - Проверка: перечисленные smoke проходят на профиле v3; `check-agent-docs` созданного проекта проверяет matrix; `template-update` на Windows не меняет заполненные matrix и quickstart.
  - Сделано: shell-загрузчик профиля (`scripts/lib/runtime-profile.sh`) принимает только v3 и отклоняет v1/v2 с подсказкой миграции; на v3 переведены фикстуры тёплых BDD/YAxUnit-контуров, `golden-baseline` и `load-cfe`. `load-cfe` снова загружает все расширения из `src/cfe` или из повторяемого `--extension` и останавливается на первом сбое. Общая функция `refresh_generated_project_surface` создаёт matrix и quickstart при `template-update` только при их отсутствии на обеих ОС. На Windows не запускалось: нет `pwsh`.

- [x] 3.7 Исправить четыре smoke, которые проходят на `main` и падают на ветке change.
  - `check-cfe-applicability.sh`, `check-cfe-config.sh`: Python-версия завершается с `invalid extension name:` при пустом имени, не пишет `summary.json` и возвращает другой код выхода, чем ожидает smoke. Вернуть поведение, описанное в спецификации, или обновить smoke, если спецификация допускает новое поведение.
  - `multi-target-extension-workspace.sh`: фикстура на профиле v2, а `load-cfe` в Python не поддерживает `--target`, хотя smoke ожидает отказ `multi-target workspace requires --target <id>`. Перевести фикстуру на v3 и вернуть выбор цели либо зафиксировать в спецификации отказ от `--target`; документация созданного проекта сейчас показывает `load-cfe.sh --target <id>`.
  - `bootstrap-agents-overlay.sh`: в созданном проекте нет строки `"configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"]`.
  - Проверка: все четыре smoke проходят; `runtime-ibcmd-validation-contract.sh` и `yaxunit-contour-contract.sh` падают и на `main`, они вне этой задачи.
  - Сделано: смоуки не ослаблялись, фикстуры только переведены на профиль v3. В Python-runtime возвращено поведение из спецификаций: проверка всех расширений в `check-cfe-*` с диагностиками по каждому, `--target` у `load-src`, `update-db`, `load-diff-src`, `load-task-src`, `load-cfe` и проверок CFE, `targetMetadata` в `export-context`. `configure-cfe-runtime-flags` `--target` пока не принимает.

- [x] 3.8 Исправить сбои, найденные при обновлении копии проекта-источника (8.3), и описать миграцию существующего проекта.
  - Добавить команду миграции таблицы поддержки сред по Р16 (Bash и PowerShell, по образцу `migrate-runtime-profile-v3`): дописать в `automation/context/runtime-support-matrix.json` недостающие `platforms.linux`/`platforms.windows` со статусом «не проверено», не меняя существующих полей, и пересобрать Markdown-версию. Сообщение проверки документации об отсутствующей записи платформы должно называть эту команду.
  - Исправить ложное срабатывание `check_skill_bindings`: `rac ` в `scripts/python/qa.py` совпадает с `trac info`; искать `rac` как отдельное слово.
  - Исправить извлечение путей в `_CURATED_PATH` (`scripts/python/agent_docs.py`): в путь не должны попадать `]` и `(` из markdown-ссылки (`[.codex/README.md](../../.codex/README.md)` даёт `.codex/README.md](../../.codex/README.md`).
  - Вернуть цель `technological-log` в `Makefile` и `make.ps1`: проект-источник её использовал, скрипт `scripts/diag/technological-log.sh` в шаблоне есть.
  - Написать `docs/migrations/project-toolkit-update.md` для проектов, созданных до этого change: перенести собственные цели из `Makefile` в `Makefile.project` (при обновлении они удаляются без предупреждения), вынести собственный текст из блока `RUNNER_AGNOSTIC_TEMPLATE` в `AGENTS.md`, заменить `make type-check` на `make verify-types`, убрать baseline basedpyright, обновить ссылки на удалённые разделы о `meta-*`/`form-*`, внести собственные `env/*.json` в `sanctionedAdditionalProfiles`, запустить миграцию таблицы поддержки сред.
  - Проверка: unit-тесты на команду миграции (добавляет только отсутствующие записи; повторный запуск ничего не меняет), на `\brac` и на извлечение пути из markdown-ссылки; повторное обновление копии проекта-источника после шагов из миграционного документа проходит `make agent-verify`.

  - Сделано: команда `scripts/template/migrate-runtime-support-matrix.{sh,ps1}` (запись платформы без доказательства запуска означает «не проверено», отдельного статуса в схеме нет), `\brac`, исправлено извлечение пути из markdown-ссылки, цель `technological-log`, документ `docs/migrations/project-toolkit-update.md`. На клоне проекта-источника после миграции таблицы ушли все сбои со стороны шаблона, кроме перечисленных в 3.9.

- [x] 3.9 Перенести недостающие функции модулей шаблона и сделать конфигурацию ruff проектной (Р18).
  - Перенести из проекта-источника в модули шаблона функции, которые по инвентарю относятся к «обобщить», но не были перенесены: `resolve_openspec_path`, `object_dict`, `object_list` (`scripts/python/common.py`, задача 3.2); `init_launch_logs`, `reap_dead_x_displays` (`scripts/python/onec_xpra.py`); `_generated_structural_contracts` (`scripts/python/agent_docs.py`); `_analyze_bsl_standalone` (`scripts/python/qa.py`, `analyze-bsl` через MCP). Обезличить, перенести их тесты.
  - Исправить `find_unclassified_python` в `scripts/python/type_checking.py`: каталоги из `exclude` проектного `pyrightconfig.json` не должны считаться неклассифицированными, как и обещает подсказка проверки.
  - По Р18: перенести правила в `scripts/qa/ruff-base.toml`, сделать `ruff.toml` создаваемым один раз (preserve-контракт, исключение из манифеста, как у `pyrightconfig.json`), добавить проверку `extend` и запрета снимать правила базы для файлов шаблона; описать шаг в `docs/migrations/project-toolkit-update.md`.
  - Перед запуском ruff проверять наличие и версию инструмента и при отсутствии печатать понятное сообщение с командой исправления вместо `Failed to spawn: ruff`.
  - Проверка: unit-тесты перенесённых функций и проверок; на клоне проекта-источника тесты проекта, импортирующие эти функции, собираются; `ruff check` с проектным `exclude` не проверяет исключённые файлы проекта; `copier-update-ready` и `make agent-verify` проходят.
  - Сделано: перенесены `resolve_openspec_path`, `object_dict`, `object_list`, `reap_dead_x_displays` (с вызовом из `direct-platform.sh`), `_generated_structural_contracts`; `find_unclassified_python` учитывает `exclude`; Р18 реализовано (`scripts/qa/ruff-base.toml`, seed-once `ruff.toml`, `check_ruff_config`, smoke `python-ruff-config-contract.sh`); перед ruff проверяется наличие инструмента. `init_launch_logs` не переносится: механизм заменён адаптером наблюдения (Р11), проект переписывает свой тест. `_analyze_bsl_standalone` вынесен в задачу 3.11 по Р19.

- [ ] 3.10 Исправить 15 тестов, упавших в первом Windows-прогоне CI (задание `fixture (windows-latest)`, ручной запуск на ветке change).
  - `test_bsl_connections.py`, `test_bsl_mcp_runtime.py`: при очищенном окружении `Path.home()` падает с `Could not determine home directory`; код не должен требовать домашний каталог, когда путь задан явно, а тест — задавать `USERPROFILE` на Windows.
  - `test_metadata_template_ops.py`, `test_metadata_template_xlsx.py`: макет с LF записывается с CRLF; запись должна сохранять исходные концы строк на любой ОС.
  - `test_ordinary_form_conversion.py` (6 тестов): сравнение короткого (`RUNNER~1`) и длинного пути, `UnicodeEncodeError: 'charmap'` при выводе дочернего процесса, поиск `src/epf/managed` с разделителями Windows.
  - `test_run_client.py` (2 теста): на Windows профиль теста включает `xpra`, доступный только на POSIX; тест должен использовать профиль для Windows или проверять отказ.
  - Проверка: задание `fixture (windows-latest)` проходит; на Linux тесты не ослаблены.

- [x] 3.11 Перевести `make analyze-bsl` на MCP `bsl-analyzer` и удалить BSL LS из шаблона (Р19).
  - Перенести из `scripts/python/qa.py` проекта-источника MCP-клиент `analyze-bsl` (`_analyze_bsl_standalone`, запуск процесса MCP, остановка дерева процессов на Windows) в обезличенном виде; реестр исключений и каталог исходников по умолчанию — без проектных идентификаторов и путей.
  - Удалить запуск jar BSL LS, его загрузку, настройки, тесты и упоминания в документации, навыках и шаблонах созданного проекта; без настроенного `bsl-analyzer` команда завершается с ошибкой и ссылкой на `docs/agent/bsl-analyzer-workspace-runbook.md`.
  - Обновить спецификации change, где `analyze-bsl` описан через BSL LS, и шаг в `docs/migrations/project-toolkit-update.md`.
  - Проверка: unit-тесты MCP-клиента на фиктивном MCP-сервере (успех, диагностики, отказ без настройки, таймаут); в шаблоне не остаётся ссылок на BSL LS (`rg -i "bsl-language-server|bsl ls|BSLLS jar"` вне истории и архива); `make agent-verify` проходит.

- [ ] 3.12 Сократить ручные шаги обновления проекта до выпуска (Р22).
  - Проверять матрицу целей `automation/context/target-matrix.json` до изменения файлов проекта: новый `update-template.sh` и Windows-путь `update_template` — до наложения файлов; `overlay-post-apply` нового релиза — первым шагом. Если проверка не прошла, вернуть рабочее дерево к `HEAD` (обновление требует чистого дерева на старте) и вывести ошибку с путём или именем расширения и ссылкой на шаг 6 документа миграции. Так обновление с `v0.3.36`, где файлы накладывает прежний скрипт проекта, тоже не оставляет проект наполовину обновлённым.
  - Создавать недостающие seed-once файлы (Р15, Р18) в `overlay-post-apply` нового релиза из файлов релиза, не перезаписывая существующие. Убрать из `docs/migrations/project-toolkit-update.md` ручное создание `ruff.toml`.
  - Добавить в начало документа миграции сводку: что обязательно сделать до обновления, что после, что можно отложить.
  - Проверка: smoke или unit-тест, где обновление проекта с несуществующим расширением в матрице завершается ошибкой и `git status` проекта чистый; тест, где обновление проекта без `ruff.toml` старым `update-template.sh` создаёт `ruff.toml` со строкой `extend`; обновление свежего клона проекта-источника без исправленной матрицы отказывает без изменений, с исправленной — проходит и создаёт `ruff.toml`.

## 4. Необязательные модули: механизм

- [x] 4.1 Добавить `make optional-module-init MODULE=<имя>` и тонкие Bash/PowerShell-обёртки по образцу `init-test-tooling`.
  - Поведение: preflight всех целевых путей, отказ без изменений при существовании, удаление скопированного при ошибке, регистрация путей как project-owned в preserve-контракте.
- [x] 4.2 Добавить `tests/smoke/optional-module-init.sh`: первая инициализация, повторная, ошибка посередине, отсутствие изменений материализованных путей после `template-update`.

## 5. Модуль площадки заказчика

- [x] 5.1 Подготовить `automation/optional/customer-site-operations/`.
  - Состав: регламент площадки, шаблоны инвентаря и профилей `*.example.json`, навыки `site-vdi-xpra`, `rdp-bash-payload`.
  - Все файлы переименованы `tnl-*` → `site-*` и обезличены.
- [x] 5.2 Перенести инструменты оператора: запуск VDI-клиента в Xpra, ввод команды со сверкой, передача файла фрагментами с SHA-256, keepalive; с их тестами на фикстурах.
- [x] 5.3 Перенести серверные обёртки на стандартной библиотеке: `site-rac` (включая `jobs-on`/`jobs-off`), `site-ibcmd`, golden/архив/DT, создание согласованной копии базы из DT и удаление неудачной копии, техжурнал, офлайн-лицензирование.
  - Добавить проверку запуска read-only команд на Python 3.7 и отказа `Refused` для базы вне профиля.
- [x] 5.4 Включить отдельной опцией модуля обёртку восстановления доступа через `v8users` (Р2) с порядком `backup → hide → restore → verify` и отказом `hide` без копии.
- [x] 5.5 Добавить `tests/smoke/customer-site-deidentified.sh`: поиск IPv4, UUID вне списка фикстур и известных проектных идентификаторов в поставляемых путях модуля.

## 6. Модуль правил КД 2.01

- [x] 6.0 Перенести ядро компилятора `scripts/migration/kd_xml_compiler/` (Р5): модель метаданных, модель правил, сериализатор КД 2.01, порядок регистрации, адаптер XML структуры.
  - Наложение CFE и построение правил из сценариев БП не переносить. Проверить `metadata_catalog.json.gz` на сведения заказчика или заменить его фикстурой.
  - Проверка: тест границы (ядро не импортирует `kd_cycle_*` и проектные модули); две сборки фикстурного сценария дают побайтно одинаковые XML, ZIP и `manifest.json` без времени и путей запуска.
- [x] 6.1 Реализовать минимальный исполнитель `scripts/migration/kd-rules-cycle`.
  - Стадии `doctor|reset|build|load|run|verify` на двух расходуемых базах; `build` вызывает компилятор; отдельная сборка `run build-rules` со статусом `rules-built`.
  - Блокировка профиля, `state.json` v2, `result.json`, манифест выпуска, `source-before/after.json`.
  - Отказ при изменении входов, узлы-расширения с режимами повтора.
- [x] 6.2 Связать `reset` с PostgreSQL golden-контуром шаблона; отказывать, если цель совпадает с эталоном или не входит в список расходуемых баз.
- [x] 6.3 Подключить блокирующие стадии к адаптеру наблюдения с порогом `runtimeStageTimeoutSeconds` профиля; верхний `observation.jsonl` и `progress.txt`.
- [x] 6.4 Подготовить `automation/optional/kd21-migration/`.
  - Состав: примеры профиля, `technical-workbench` сценария, матрицы и ожидаемого результата, обработка выгрузки структуры `metadata-exporter`, регламент `kd21-rules-workbench-runbook.md`, обобщённый навык `1c-prepare-manual-migration-bases`, заготовка раздела `## Влияние на миграцию`.
- [x] 6.5 Добавить `tests/smoke/kd21-workbench-contract.sh` на фикстурном исполнителе стадий.
  - Проверки: отказ при совпадении цели с эталоном, `profile is already running`, `inputs changed`, остановка после `failed`, `rules-built` без обращения к базам, `workbench-run-passed`, `same generation`, расхождение хешей с baseline, неготовая зависимость узла.

## 7. Поверхность создаваемого проекта и документация

- [x] 7.1 Обновить `template-managed-paths.txt`, preserve-контракт, `recommended-skills`, runtime support matrix и generated-project guidance для новых команд и модулей.
- [x] 7.2 Построить зеркало `.claude/skills/` командой `make sync-claude-skills` и выполнить `make export-context-write`.

## 8. Финальная проверка

- [x] 8.1 Выполнить `openspec validate import-project-toolkit-and-migration-workflows --strict --no-interactive`.
- [x] 8.2 Выполнить `make agent-verify` и `tests/smoke/copier-update-ready.sh` в исходнике шаблона.
- [x] 8.3 Проверить `copier copy` в пустой каталог и `template-update` копии проекта-источника; убедиться, что после обновления материализованные модули и project-owned пути не изменены.
  - Сделано 2026-10-10: свежий клон проекта-источника обновлён `template-update` с `v0.3.36`; модуль площадки материализован, модуль КД отказал без изменений (у проекта свои `migration/kd21/` и навык); после обновления на новый ref 140 файлов материализованных и project-owned путей побайтно не изменились. `copier copy` в пустой каталог: заготовки модулей есть, модули не материализованы, `make agent-verify` проходит. Найдено и описано в `docs/migrations/project-toolkit-update.md`: матрица целей проекта ссылается на расширение из `src/cfe/_templates/` (шаг 6 до обновления); первое обновление с `v0.3.36` не создаёт `ruff.toml`.
- [x] 8.4 Проверить вручную список поставляемых путей необязательного модуля площадки на отсутствие сведений заказчика.
  - Сделано 2026-10-10: профили-примеры, регламенты, инвентарь и навыки `site-*` содержат только вымышленные узлы `*.example`, UUID-заглушки и общие пороги. Встроенный стоп-лист имён проекта-источника удалён из smoke: проект передаёт свои имена через `SITE_DEIDENTIFY_DENYLIST`.
