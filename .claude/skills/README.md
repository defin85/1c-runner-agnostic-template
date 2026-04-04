# Project-Scoped 1C Skills

Эти skills являются project-scoped фасадом над versioned repo scripts.
Codex-facing equivalents лежат в [.agents/skills/README.md](../../.agents/skills/README.md).

## Native Runner-Agnostic Skills

| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |
| --- | --- | --- | --- | --- |
| Этот скилл MUST быть вызван, когда пользователь просит создать информационную базу через канонический runtime contract проекта. | `1c-create-ib` | `1c-create-ib` | `./scripts/platform/create-ib.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит diff исходников или диагностический сравнительный прогон через канонический contract проекта. | `1c-diff-src` | `1c-diff-src` | `./scripts/platform/diff-src.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит диагностировать готовность runtime-профиля, adapter config и базовых зависимостей проекта. | `1c-doctor` | `1c-doctor` | `./scripts/diag/doctor.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит выгрузить конфигурацию или расширение в исходники через канонический runtime contract проекта. | `1c-dump-src` | `1c-dump-src` | `./scripts/platform/dump-src.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит загрузить в ИБ только текущие git-backed изменения исходников через repo-owned bridge. | `1c-load-diff-src` | `1c-load-diff-src` | `./scripts/platform/load-diff-src.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит загрузить исходники в информационную базу через канонический runtime contract проекта. | `1c-load-src` | `1c-load-src` | `./scripts/platform/load-src.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит загрузить в ИБ уже закомиченные изменения задачи через repo-owned task bridge. | `1c-load-task-src` | `1c-load-task-src` | `./scripts/platform/load-task-src.sh` | native template capability |
| Этот скилл SHOULD быть вызван, когда пользователь просит опубликовать HTTP-сервис или веб-контур через канонический repo entrypoint. | `1c-publish-http` | `1c-publish-http` | `./scripts/platform/publish-http.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит запустить BDD / acceptance-контур через канонический test entrypoint проекта. | `1c-run-bdd` | `1c-run-bdd` | `./scripts/test/run-bdd.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит запустить smoke-контур через канонический test entrypoint проекта. | `1c-run-smoke` | `1c-run-smoke` | `./scripts/test/run-smoke.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит запустить xUnit-контур через канонический test entrypoint проекта. | `1c-run-xunit` | `1c-run-xunit` | `./scripts/test/run-xunit.sh` | native template capability |
| Этот скилл MUST быть вызван, когда пользователь просит применить изменения основной конфигурации к конфигурации базы данных. | `1c-update-db` | `1c-update-db` | `./scripts/platform/update-db.sh` | native template capability |

## Imported Compatibility Pack (`cc-1c-skills`)

- Upstream source: `git@github.com:Nikolay-Shirokov/cc-1c-skills.git`
- Upstream commit: `eebc2a06792c6c0263ce02bb6c63b8a4579134d1`
- Vendor root: [`automation/vendor/cc-1c-skills/README.md`](../../automation/vendor/cc-1c-skills/README.md)

| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |
| --- | --- | --- | --- | --- |
| Точечное редактирование конфигурации 1С. Используй когда нужно изменить свойства конфигурации, добавить или удалить объект из состава, настроить роли по умолчанию | `cf-edit` | `cf-edit` | `./scripts/skills/run-imported-skill.sh cf-edit` | python |
| Анализ структуры конфигурации 1С — свойства, состав, счётчики объектов. Используй для обзора конфигурации — какие объекты есть, сколько их, какие настройки | `cf-info` | `cf-info` | `./scripts/skills/run-imported-skill.sh cf-info` | python |
| Создать пустую конфигурацию 1С (scaffold XML-исходников). Используй когда нужно начать новую конфигурацию с нуля | `cf-init` | `cf-init` | `./scripts/skills/run-imported-skill.sh cf-init` | python |
| Валидация конфигурации 1С. Используй после создания или модификации конфигурации для проверки корректности | `cf-validate` | `cf-validate` | `./scripts/skills/run-imported-skill.sh cf-validate` | python |
| Заимствование объектов из конфигурации 1С в расширение (CFE). Используй когда нужно перехватить метод, изменить форму или добавить реквизит к существующему объекту конфигурации | `cfe-borrow` | `cfe-borrow` | `./scripts/skills/run-imported-skill.sh cfe-borrow` | python |
| Анализ расширения конфигурации 1С (CFE) — состав, заимствованные объекты, перехватчики, проверка переноса. Используй когда нужно понять что содержит расширение или проверить перенесены ли вставки в конфигурацию | `cfe-diff` | `cfe-diff` | `./scripts/skills/run-imported-skill.sh cfe-diff` | python |
| Создать расширение конфигурации 1С (CFE) — scaffold XML-исходников. Используй когда нужно создать новое расширение для исправления, доработки или дополнения конфигурации | `cfe-init` | `cfe-init` | `./scripts/skills/run-imported-skill.sh cfe-init` | python |
| Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального | `cfe-patch-method` | `cfe-patch-method` | `./scripts/skills/run-imported-skill.sh cfe-patch-method` | python |
| Валидация расширения конфигурации 1С (CFE). Используй после создания или модификации расширения для проверки корректности | `cfe-validate` | `cfe-validate` | `./scripts/skills/run-imported-skill.sh cfe-validate` | python |
| Создание информационной базы 1С. Используй когда пользователь просит создать базу, новую ИБ, пустую базу | `db-create` | `db-create` | `./scripts/skills/run-imported-skill.sh db-create` | native-alias; prefer 1c-create-ib |
| Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит выгрузить конфигурацию в CF, сохранить конфигурацию, сделать бэкап CF | `db-dump-cf` | `db-dump-cf` | `./scripts/skills/run-imported-skill.sh db-dump-cf` | python |
| Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles | `db-dump-xml` | `db-dump-xml` | `./scripts/skills/run-imported-skill.sh db-dump-xml` | python |
| Управление реестром баз данных 1С (.v8-project.json). Используй когда пользователь говорит про базы данных, список баз, "добавь базу", "какие базы есть" | `db-list` | `db-list` | `./scripts/skills/run-imported-skill.sh db-list` | reference |
| Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF | `db-load-cf` | `db-load-cf` | `./scripts/skills/run-imported-skill.sh db-load-cf` | python |
| Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита | `db-load-git` | `db-load-git` | `./scripts/skills/run-imported-skill.sh db-load-git` | python; prefer 1c-load-diff-src, 1c-load-task-src |
| Загрузка конфигурации 1С из XML-файлов. Используй когда пользователь просит загрузить конфигурацию из файлов, XML, исходников, LoadConfigFromFiles | `db-load-xml` | `db-load-xml` | `./scripts/skills/run-imported-skill.sh db-load-xml` | python |
| Запуск 1С:Предприятие. Используй когда пользователь просит запустить 1С, открыть базу, запустить предприятие | `db-run` | `db-run` | `./scripts/skills/run-imported-skill.sh db-run` | python |
| Обновление конфигурации базы данных 1С. Используй когда пользователь просит обновить БД, применить конфигурацию, UpdateDBCfg | `db-update` | `db-update` | `./scripts/skills/run-imported-skill.sh db-update` | native-alias; prefer 1c-update-db |
| Добавить управляемую форму к внешней обработке 1С | `epf-add-form` | `epf-add-form` | `./scripts/skills/run-imported-skill.sh epf-add-form` | python |
| Добавить команду в дополнительную обработку БСП | `epf-bsp-add-command` | `epf-bsp-add-command` | `./scripts/skills/run-imported-skill.sh epf-bsp-add-command` | reference |
| Добавить функцию регистрации БСП (СведенияОВнешнейОбработке) в модуль объекта обработки | `epf-bsp-init` | `epf-bsp-init` | `./scripts/skills/run-imported-skill.sh epf-bsp-init` | reference |
| Собрать внешнюю обработку 1С (EPF/ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать обработку или получить EPF/ERF файл из исходников | `epf-build` | `epf-build` | `./scripts/skills/run-imported-skill.sh epf-build` | python |
| Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать обработку, получить исходники из EPF/ERF файла | `epf-dump` | `epf-dump` | `./scripts/skills/run-imported-skill.sh epf-dump` | python |
| Создать пустую внешнюю обработку 1С (scaffold XML-исходников) | `epf-init` | `epf-init` | `./scripts/skills/run-imported-skill.sh epf-init` | python |
| Валидация внешней обработки 1С (EPF). Используй после создания или модификации обработки для проверки корректности | `epf-validate` | `epf-validate` | `./scripts/skills/run-imported-skill.sh epf-validate` | python |
| Собрать внешний отчёт 1С (ERF) из XML-исходников. Используй когда пользователь просит собрать, скомпилировать отчёт или получить ERF файл из исходников | `erf-build` | `erf-build` | `./scripts/skills/run-imported-skill.sh erf-build` | python |
| Разобрать ERF-файл отчёта 1С в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать отчёт, получить исходники из ERF файла | `erf-dump` | `erf-dump` | `./scripts/skills/run-imported-skill.sh erf-dump` | python |
| Создать пустой внешний отчёт 1С (scaffold XML-исходников) | `erf-init` | `erf-init` | `./scripts/skills/run-imported-skill.sh erf-init` | python |
| Валидация внешнего отчёта 1С (ERF). Используй после создания или модификации отчёта для проверки корректности | `erf-validate` | `erf-validate` | `./scripts/skills/run-imported-skill.sh erf-validate` | python |
| Добавить управляемую форму к объекту конфигурации 1С | `form-add` | `form-add` | `./scripts/skills/run-imported-skill.sh form-add` | python |
| Компиляция управляемой формы 1С из компактного JSON-определения. Используй когда нужно создать форму с нуля по описанию элементов | `form-compile` | `form-compile` | `./scripts/skills/run-imported-skill.sh form-compile` | python |
| Добавление элементов, реквизитов и команд в существующую управляемую форму 1С. Используй когда нужно точечно модифицировать готовую форму | `form-edit` | `form-edit` | `./scripts/skills/run-imported-skill.sh form-edit` | python |
| Анализ структуры управляемой формы 1С (Form.xml) — элементы, реквизиты, команды, события. Используй для понимания формы — при написании модуля формы, анализе обработчиков и элементов | `form-info` | `form-info` | `./scripts/skills/run-imported-skill.sh form-info` | python |
| Справочник паттернов компоновки управляемых форм 1С. Используй как справочник при проектировании форм — архетипы, конвенции, продвинутые приёмы | `form-patterns` | `form-patterns` | `./scripts/skills/run-imported-skill.sh form-patterns` | reference |
| Удалить форму из объекта 1С (обработка, отчёт, справочник, документ и др.) | `form-remove` | `form-remove` | `./scripts/skills/run-imported-skill.sh form-remove` | python |
| Валидация управляемой формы 1С. Используй после создания или модификации формы для проверки корректности. При наличии BaseForm автоматически проверяет callType и ID расширений | `form-validate` | `form-validate` | `./scripts/skills/run-imported-skill.sh form-validate` | python |
| Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту | `help-add` | `help-add` | `./scripts/skills/run-imported-skill.sh help-add` | python |
| Наложить пронумерованную сетку на изображение для определения пропорций колонок | `img-grid` | `img-grid` | `./scripts/skills/run-imported-skill.sh img-grid` | python |
| Настройка командного интерфейса подсистемы 1С. Используй когда нужно скрыть или показать команды, разместить в группах, настроить порядок | `interface-edit` | `interface-edit` | `./scripts/skills/run-imported-skill.sh interface-edit` | python |
| Валидация командного интерфейса 1С. Используй после настройки командного интерфейса подсистемы для проверки корректности | `interface-validate` | `interface-validate` | `./scripts/skills/run-imported-skill.sh interface-validate` | python |
| Создать объект метаданных 1С. Используй когда пользователь просит создать или добавить справочник, документ, регистр, перечисление, константу, общий модуль, обработку, отчёт и др. | `meta-compile` | `meta-compile` | `./scripts/skills/run-imported-skill.sh meta-compile` | python |
| Точечное редактирование объекта метаданных 1С. Используй когда нужно добавить, удалить или изменить реквизиты, табличные части, измерения, ресурсы или свойства существующего объекта конфигурации | `meta-edit` | `meta-edit` | `./scripts/skills/run-imported-skill.sh meta-edit` | python |
| Анализ структуры объекта метаданных 1С из XML-выгрузки — реквизиты, табличные части, формы, движения, типы. Используй для изучения структуры объектов (вместо чтения XML-файлов напрямую) и как подготовительный шаг при написании запросов и кода, работающего с объектами | `meta-info` | `meta-info` | `./scripts/skills/run-imported-skill.sh meta-info` | python |
| Удалить объект метаданных из конфигурации 1С. Используй когда пользователь просит удалить, убрать объект из конфигурации | `meta-remove` | `meta-remove` | `./scripts/skills/run-imported-skill.sh meta-remove` | python |
| Валидация объекта метаданных 1С. Используй после создания или модификации объекта конфигурации для проверки корректности | `meta-validate` | `meta-validate` | `./scripts/skills/run-imported-skill.sh meta-validate` | python |
| Компиляция табличного документа (MXL) из JSON-определения. Используй когда нужно создать макет печатной формы | `mxl-compile` | `mxl-compile` | `./scripts/skills/run-imported-skill.sh mxl-compile` | python |
| Декомпиляция табличного документа (MXL) в JSON-определение. Используй когда нужно получить редактируемое описание существующего макета | `mxl-decompile` | `mxl-decompile` | `./scripts/skills/run-imported-skill.sh mxl-decompile` | python |
| Анализ структуры макета табличного документа (MXL) — области, параметры, наборы колонок. Используй при разработке печати — получить области и заполняемые параметры макета | `mxl-info` | `mxl-info` | `./scripts/skills/run-imported-skill.sh mxl-info` | python |
| Валидация макета табличного документа (MXL). Используй после создания или модификации макета для проверки корректности | `mxl-validate` | `mxl-validate` | `./scripts/skills/run-imported-skill.sh mxl-validate` | python |
| Создание роли 1С из описания прав. Используй когда нужно создать новую роль с набором прав на объекты | `role-compile` | `role-compile` | `./scripts/skills/run-imported-skill.sh role-compile` | python |
| Компактная сводка прав роли 1С из Rights.xml — объекты, права, RLS, шаблоны ограничений. Используй для аудита прав — какие объекты и действия доступны, ограничения RLS | `role-info` | `role-info` | `./scripts/skills/run-imported-skill.sh role-info` | python |
| Валидация роли 1С. Используй после создания или модификации роли для проверки корректности | `role-validate` | `role-validate` | `./scripts/skills/run-imported-skill.sh role-validate` | python |
| Компиляция схемы компоновки данных 1С (СКД) из компактного JSON-определения. Используй когда нужно создать СКД с нуля | `skd-compile` | `skd-compile` | `./scripts/skills/run-imported-skill.sh skd-compile` | python |
| Точечное редактирование схемы компоновки данных 1С (СКД). Используй когда нужно модифицировать существующую СКД — добавить поля, итоги, фильтры, параметры, изменить текст запроса | `skd-edit` | `skd-edit` | `./scripts/skills/run-imported-skill.sh skd-edit` | python |
| Анализ структуры схемы компоновки данных 1С (СКД) — наборы, поля, параметры, варианты. Используй для понимания отчёта — источник данных (запрос), доступные поля, параметры | `skd-info` | `skd-info` | `./scripts/skills/run-imported-skill.sh skd-info` | python |
| Валидация схемы компоновки данных 1С (СКД). Используй после создания или модификации СКД для проверки корректности | `skd-validate` | `skd-validate` | `./scripts/skills/run-imported-skill.sh skd-validate` | python |
| Создать подсистему 1С — XML-исходники из JSON-определения. Используй когда пользователь просит добавить подсистему (раздел) в конфигурацию | `subsystem-compile` | `subsystem-compile` | `./scripts/skills/run-imported-skill.sh subsystem-compile` | python |
| Точечное редактирование подсистемы 1С. Используй когда нужно добавить или удалить объекты из подсистемы, управлять дочерними подсистемами или изменить свойства | `subsystem-edit` | `subsystem-edit` | `./scripts/skills/run-imported-skill.sh subsystem-edit` | python |
| Анализ структуры подсистемы 1С из XML-выгрузки — состав, дочерние подсистемы, командный интерфейс, дерево иерархии. Используй для изучения структуры подсистем и навигации по конфигурации | `subsystem-info` | `subsystem-info` | `./scripts/skills/run-imported-skill.sh subsystem-info` | python |
| Валидация подсистемы 1С. Используй после создания или модификации подсистемы для проверки корректности | `subsystem-validate` | `subsystem-validate` | `./scripts/skills/run-imported-skill.sh subsystem-validate` | python |
| Добавить макет к объекту 1С (обработка, отчёт, справочник, документ и др.) | `template-add` | `template-add` | `./scripts/skills/run-imported-skill.sh template-add` | python |
| Удалить макет из объекта 1С (обработка, отчёт, справочник, документ и др.) | `template-remove` | `template-remove` | `./scripts/skills/run-imported-skill.sh template-remove` | python |
| Статус Apache и веб-публикаций 1С — запущен ли сервер, какие базы опубликованы, ошибки. Используй когда пользователь спрашивает про статус веб-сервера, опубликованные базы, работает ли Apache | `web-info` | `web-info` | `./scripts/skills/run-imported-skill.sh web-info` | python |
| Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере | `web-publish` | `web-publish` | `./scripts/skills/run-imported-skill.sh web-publish` | native-alias; prefer 1c-publish-http |
| Остановка Apache HTTP Server. Используй когда пользователь просит остановить веб-сервер, Apache, прекратить веб-публикацию | `web-stop` | `web-stop` | `./scripts/skills/run-imported-skill.sh web-stop` | python |
| Тестирование 1С через веб-клиент — автоматизация действий в браузере. Используй когда пользователь просит проверить, протестировать, автоматизировать действия в 1С через браузер | `web-test` | `web-test` | `./scripts/skills/run-imported-skill.sh web-test` | node |
| Удаление веб-публикации 1С из Apache. Используй когда пользователь просит убрать публикацию, удалить веб-доступ к базе | `web-unpublish` | `web-unpublish` | `./scripts/skills/run-imported-skill.sh web-unpublish` | python |

## Rules

- Source of truth для выполнения находится в `scripts/`, а не в `SKILL.md`.
- Если нужно поменять flags, artifact contract или adapter behavior imported skills, сначала меняйте repo-owned dispatcher или vendored helper.
- Native runner-agnostic skills остаются предпочтительным surface для template-owned runtime workflows.
