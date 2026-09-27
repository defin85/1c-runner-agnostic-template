Состояние проектирования: решения Р1–Р4 приняты (`design.md`); следующий шаг — инвентарь 0.2. Реализация не начата.
Порядок выпуска (Р4): сначала этапы 0–3 и 7 для базового набора, затем 4–6.

## 0. Решения и инвентарь

- [x] 0.1 Получить решения по открытым вопросам 1–4 из `proposal.md` и записать их в `design.md` как принятые решения.
- [ ] 0.2 Составить `inventory.md` сверки 179 расходящихся template-managed файлов проекта-источника относительно `v0.3.36`.
  - Для каждого файла записать решение `перенести|обобщить|оставить в проекте|уже есть` и причину.
  - Проверка: число записей равно числу расходящихся файлов; у каждой записи есть решение.

## 1. Наблюдение длительных операций

- [ ] 1.1 Перенести общий адаптер наблюдения и навык `1c-observe-run`: `observation.jsonl` schema v1, `progress.txt`, terminal-секция `summary.json`, остановка по `runtimeStageTimeoutSeconds`.
- [ ] 1.2 Перенести `scripts/diag/technological-log.sh` с operation cursor и восстановлением исходного `logcfg.xml`.
- [ ] 1.3 Подключить адаптер к `direct-platform.sh`, `db-run`, EPF/ERF build/dump и операциям с временными файловыми ИБ.
- [ ] 1.4 Добавить `tests/smoke/observation-contract.sh`.
  - Проверка на фикстурных процессах: ровно один terminal, `failed` при отсутствии результата, остановка при неизменном прогрессе, восстановление `logcfg.xml` после ошибки.

## 2. Проверка BSL и инструментарий разработки

- [ ] 2.1 Перенести навык `1c-check-bsl` и `scripts/platform/check-cf-modules.sh` с выводом версии платформы и режима совместимости в результат.
- [ ] 2.2 Добавить `tests/smoke/check-bsl-routing.sh`: выбор модулей, маршрутизация в анализатор или платформу, итог `синтаксис: не проверен` при недоступности, без разбора BSL.
- [ ] 2.3 Перенести `scripts/python/metadata*.py` с тестами `tests/python/` и навыки `metadata-use`, `metadata-cli-development`.
- [ ] 2.4 Перенести `ordinary_form_conversion.py`, `v8unpack_container.py`, `v8unpack_erf_form.py`, `cfe_templates.py`, навыки `ordinary-form-workflow`, `prepare-external-artifact`, `cfe-form-workflow`, `v8unpack` и `docs/agent/ordinary-form-conversion-runbook.md`, обезличив примеры.
- [ ] 2.5 Перенести `v8std.py`, `scripts/tools/v8std-fetch`, `v8std-search` с кешем в `.artifacts/v8std` / `V8STD_CACHE_ROOT`.
- [ ] 2.6 Перенести `docs/agent/repository-search-runbook.md`, `docs/agent/bsl-analyzer-workspace-runbook.md`, навыки `1c-rac-operations`, `1c-linux-crash-diagnostics`, `legacy-customization-port`, удалив проектные имена.

## 3. Качество репозитория

- [ ] 3.1 Добавить в `check-skill-bindings` проверку существования путей из `SKILL.md` с учётом необязательных модулей; добавить `tests/smoke/skill-bindings-paths.sh`.
- [ ] 3.2 Добавить basedpyright gate.
  - Состав: `pyrightconfig.json`, `scripts/python/type_checking.py`, `scripts/qa/type-check.sh|.ps1`, baseline, `tests/smoke/python-type-checking-contract.sh`.
  - Добавить dev-зависимость в `pyproject.toml`/`uv.lock`, сделать `requirements-dev.txt` производным export.
- [ ] 3.3 Перенести общие правки template-managed сценариев по решениям `inventory.md`.
  - Для `runtime.py` — сопоставить с модулями `runtime_*`.
  - Проверка: существующие smoke runtime-контура и `copier-update-ready.sh` проходят.

## 4. Необязательные модули: механизм

- [ ] 4.1 Добавить `make optional-module-init MODULE=<имя>` и тонкие Bash/PowerShell-обёртки по образцу `init-test-tooling`.
  - Поведение: preflight всех целевых путей, отказ без изменений при существовании, удаление скопированного при ошибке, регистрация путей как project-owned в preserve-контракте.
- [ ] 4.2 Добавить `tests/smoke/optional-module-init.sh`: первая инициализация, повторная, ошибка посередине, отсутствие изменений материализованных путей после `template-update`.

## 5. Модуль площадки заказчика

- [ ] 5.1 Подготовить `automation/optional/customer-site-operations/`.
  - Состав: регламент площадки, шаблоны инвентаря и профилей `*.example.json`, навыки `site-vdi-xpra`, `rdp-bash-payload`.
  - Все файлы переименованы `tnl-*` → `site-*` и обезличены.
- [ ] 5.2 Перенести инструменты оператора: запуск VDI-клиента в Xpra, ввод команды со сверкой, передача файла фрагментами с SHA-256, keepalive; с их тестами на фикстурах.
- [ ] 5.3 Перенести серверные обёртки (`site-rac`, `site-ibcmd`, golden/архив/DT, техжурнал, офлайн-лицензирование) на стандартной библиотеке.
  - Добавить проверку запуска read-only команд на Python 3.7 и отказа `Refused` для базы вне профиля.
- [ ] 5.4 Включить отдельной опцией модуля обёртку восстановления доступа через `v8users` (Р2) с порядком `backup → hide → restore → verify` и отказом `hide` без копии.
- [ ] 5.5 Добавить `tests/smoke/customer-site-deidentified.sh`: поиск IPv4, UUID вне списка фикстур и известных проектных идентификаторов в поставляемых путях модуля.

## 6. Модуль правил КД 2.1

- [ ] 6.1 Реализовать минимальный исполнитель `scripts/migration/kd-rules-cycle`.
  - Стадии `preflight|reset|build|load|run|verify`, блокировка профиля, `state.json` v2, `result.json`, манифест выпуска, `source-before/after.json`.
  - Отказ при изменении входов, узлы-расширения с режимами повтора.
- [ ] 6.2 Связать `reset` с PostgreSQL golden-контуром шаблона; отказывать, если цель совпадает с эталоном или не входит в список расходуемых баз.
- [ ] 6.3 Подключить блокирующие стадии к адаптеру наблюдения; верхний `observation.jsonl` и `progress.txt`.
- [ ] 6.4 Подготовить `automation/optional/kd21-migration/`.
  - Состав: примеры профиля, `technical-workbench` сценария, матрицы и ожидаемого результата, регламент `kd21-rules-workbench-runbook.md`, обобщённый навык `1c-prepare-manual-migration-bases`, заготовка раздела `## Влияние на миграцию`.
- [ ] 6.5 Добавить `tests/smoke/kd21-workbench-contract.sh` на фикстурном исполнителе стадий.
  - Проверки: отказ при совпадении цели с эталоном, `profile is already running`, `inputs changed`, остановка после `failed`, `workbench-run-passed`, `same generation`, расхождение хешей с baseline, неготовая зависимость узла.

## 7. Поверхность создаваемого проекта и документация

- [ ] 7.1 Обновить `template-managed-paths.txt`, preserve-контракт, `recommended-skills`, runtime support matrix и generated-project guidance для новых команд и модулей.
- [ ] 7.2 Зеркалировать новые навыки в `.claude/skills/` и выполнить `make export-context-write`.

## 8. Финальная проверка

- [ ] 8.1 Выполнить `openspec validate import-project-toolkit-and-migration-workflows --strict --no-interactive`.
- [ ] 8.2 Выполнить `make agent-verify` и `tests/smoke/copier-update-ready.sh` в исходнике шаблона.
- [ ] 8.3 Проверить `copier copy` в пустой каталог и `template-update` копии проекта-источника; убедиться, что после обновления материализованные модули и project-owned пути не изменены.
- [ ] 8.4 Проверить вручную список поставляемых путей необязательного модуля площадки на отсутствие сведений заказчика.
