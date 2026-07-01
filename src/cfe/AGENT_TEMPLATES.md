# Agent Templates For Configuration Extensions

Документ фиксирует копируемые source-only заготовки расширений из `src/cfe/_templates`.

## Источники паттернов

- Расширения с `ConfigurationExtensionPurpose=Patch` используйте для точечных исправлений поверх типовой конфигурации.
- Расширения с `ConfigurationExtensionPurpose=Customization` используйте для доработочных расширений.
- Минимальный валидный scaffold расширения состоит из `Configuration.xml`, `Languages/Русский.xml` и роли по умолчанию в `Roles/`.

## Готовые source-only заготовки

- `_templates/TemplatePatchExtension` — расширение-исправление с `ConfigurationExtensionPurpose=Patch`.
- `_templates/TemplateCustomizationExtension` — расширение-доработка с `ConfigurationExtensionPurpose=Customization`.

## Правила адаптации

1. Скопируйте нужный каталог в `src/cfe/<ИмяРасширения>`.
2. Замените `TemplatePatchExtension` или `TemplateCustomizationExtension` на новое имя расширения во всех XML.
3. Переименуйте роль `<Имя>_ОсновнаяРоль` и файл роли в `Roles/`.
4. Сгенерируйте новые UUID для `Configuration`, `Language`, `Role` и всех `xr:ObjectId`, если копируете шаблон в тот же source tree.
5. Если расширение будет загружаться в реальную базу, замените `ExtendedConfigurationObject` языка `Русский` на UUID языка базовой конфигурации. Его можно взять из `src/cf/Languages/Русский.xml` или создать scaffold через `cfe-init -ConfigPath src/cf`.
6. При добавлении заимствованных объектов указывайте `ObjectBelonging=Adopted` и `ExtendedConfigurationObject` целевого объекта базовой конфигурации.
7. Держите `ChildObjects` синхронно с файлами и директориями расширения.

## Минимальная проверка

1. `./scripts/skills/run-imported-skill.sh cfe-validate -ExtensionPath src/cfe/<ИмяРасширения> -Detailed`
2. Для измененных форм дополнительно запускайте `form-validate`.
3. После добавления файлов в `src/cfe` обновляйте generated context через `make export-context-write`.
4. Закрывающая проверка: `git diff --check`, `make export-context-check`, `make agent-verify`.
