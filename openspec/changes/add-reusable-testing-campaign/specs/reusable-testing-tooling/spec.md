## ADDED Requirements

### Requirement: Переиспользуемый 1С-контур Vanessa
Шаблон SHALL поставлять под `automation/testing/templates/` исходную заготовку инфраструктурного расширения Vanessa, реализующую загрузку Vanessa Automation Single, запуск по параметру и файловый протокол `RUN`/`STOP` с состояниями готовности, завершения и ошибки. Заготовка SHALL исключать ссылки на Delans, прикладные сценарии и заимствованные объекты с UUID базовой конфигурации.

#### Scenario: Инициализация контура Vanessa
- **WHEN** оператор запускает `init-test-tooling` в проекте без целевого расширения
- **THEN** команда создаёт project-owned расширение под `src/cfe` из заготовки без объектов и идентификаторов Delans

#### Scenario: Существующее проектное расширение
- **WHEN** любой выбранный целевой каталог уже существует
- **THEN** команда завершается с ошибкой до копирования и не изменяет ни один каталог `src/cfe`

### Requirement: Каркас проектных тестов YAxUnit
Шаблон SHALL поставлять обезличенную заготовку `ProjectYAxUnitTests` с подсистемой подключения тестовых модулей и минимальным примером динамической регистрации без ссылок на метаданные Delans. При создании project-owned расширения команда SHALL пересоздать внутренне согласованные UUID заготовки и сохранить ссылки между её XML-файлами.

#### Scenario: Создание проектного расширения тестов
- **WHEN** оператор передаёт допустимое имя проектного расширения тестов
- **THEN** команда создаёт самодостаточные исходники с новым именем и новыми согласованными UUID, готовые для добавления проектных тестовых модулей

### Requirement: Закреплённые upstream-source расширения
Шаблон SHALL хранить проверенные source-only снимки YAxUnit 25.12 (Apache-2.0) и VAExtension 1.29 (BSD-3-Clause) под `automation/testing/vendor/` вместе с лицензиями, upstream NOTICE/атрибуцией при наличии и `UPSTREAM.json`. Provenance SHALL включать repository/release URL, tag, имя и SHA-256 официального CFE asset, исходный Delans Git tree id и детерминированный source-tree SHA-256 по отсортированным относительным путям и хешам файлов. YAxUnit SHALL ссылаться на CFE SHA-256 `805a2277c997a3c24be0b0d080696479e91e4a15ed7e27aaf3991a7346522d70` и Git tree `9df32496af0985735968594c126a7e4bffb54e18`; VAExtension — на CFE SHA-256 `fc557bb23371a37dbe22a7a7a83e28f6db75b57f87e8802028cf1f90c4e00605` и Git tree `2d8b3b72df05c0282403f5b0c34d2235e2369462`. `init-test-tooling` SHALL копировать эти снимки в `src/cfe/YAxUnit` и `src/cfe/VAExtension` без изменения upstream UUID.

#### Scenario: Автономная инициализация исходников
- **WHEN** оператор запускает `init-test-tooling` без доступа к сети и целевые каталоги отсутствуют
- **THEN** заготовки VATestContour и ProjectYAxUnitTests и закреплённые YAxUnit/VAExtension создаются из содержимого репозитория

### Requirement: Воспроизводимая установка Vanessa Automation Single
Шаблон SHALL закреплять Vanessa Automation release `1.2.043.28`, asset `vanessa-automation-single.1.2.043.28.zip`, ZIP SHA-256 `cd0a017a8af69328f471f628ac1367a0e5148f790df9c28c318348b30f08f32a` и SHA-256 `97cf472753c44f3b391062ad918f01a6e0a5932f230570c3102ab22e44df7a48` для извлечённого `vanessa-automation-single.epf`. `install-test-tooling` SHALL принимать официальный URL либо `--archive <local-zip>`, безопасно извлекать ровно ожидаемый обычный файл, проверять оба хеша до атомарной публикации в `.artifacts/testing/vanessa/1.2.043.28/` и сохранять ранее установленные версии.

#### Scenario: Успешная установка
- **WHEN** загруженный и извлечённый EPF соответствует закреплённой контрольной сумме
- **THEN** он атомарно публикуется по versioned-пути, а повторный запуск переиспользует идентичный файл

#### Scenario: Ошибка загрузки или контрольной суммы
- **WHEN** загрузка, распаковка или проверка SHA-256 завершается ошибкой
- **THEN** команда завершается с ошибкой и не заменяет ни один ранее проверенный EPF

### Requirement: Явное владение и обновление тестового инструментария
Заготовки, vendor-source, манифест и команды SHALL быть template-managed, а созданные каталоги под `src/cfe`, состояние кампаний и `.artifacts/testing/` SHALL оставаться вне автоматического overlay-применения. Инициализация исходников и установка бинарника SHALL выполняться только явными командами и не SHALL запускаться как побочный эффект bootstrap или template update.

#### Scenario: Обновление существующего проекта
- **WHEN** проект с адаптированными тестовыми расширениями и установленным EPF применяет новый overlay
- **THEN** обновляются только template-managed заготовки, vendor-source и команды, а `src/cfe`, кампании и `.artifacts/testing/` остаются неизменными

### Requirement: Проверка переносимости и runtime-совместимости
No-1C baseline SHALL проверять структуру заготовок, происхождение vendor-source, отсутствие строк Delans и известных UUID прототипа, защиту существующих каталогов и fail-closed установку на локальном fixture-архиве. До объявления 1С-контура готовым provisioned-runtime gate SHALL выполнить `check-cfe-config`, `check-cfe-applicability`, загрузку четырёх расширений и минимальные запуски YAxUnit и Vanessa BDD в Delans на target `delans_ut_26_bdd` и `delans_unf_bdd`.

#### Scenario: Статический контракт проходит без 1С
- **WHEN** выполняется `make agent-verify`
- **THEN** он проверяет переносимость, владение и локальную установку без сети и лицензированной платформы

#### Scenario: Выпуск изменяет исходники или версию зависимости
- **WHEN** меняется VATestContour, ProjectYAxUnitTests, YAxUnit, VAExtension или Vanessa Automation Single
- **THEN** выпуск не считается runtime-проверенным без успешного provisioned-runtime gate на `delans_ut_26_bdd` и `delans_unf_bdd`
