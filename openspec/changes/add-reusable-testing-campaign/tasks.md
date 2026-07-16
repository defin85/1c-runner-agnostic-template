## 1. Контракт кампании

- [ ] 1.1 Добавить `scripts/python/testing_campaign.py`, подключить команды `init`, `use`, `next`, `set` и `status` к существующему Python CLI и создать тонкие `scripts/test/testing-campaign.sh` и `.ps1`.
- [ ] 1.2 Реализовать schemaVersion 1, UTC RFC 3339, regex/уникальность id, запрет неизвестных полей, точную схему selector-ов, проверку project-relative путей/символических ссылок, полный граф переходов, обязательный `resultDir` для `done` и атомарную замену через `os.replace`.
- [ ] 1.3 Добавить русскоязычную инструкцию формата кампании, single-writer ограничения, состояний, переходов, приоритета очереди, fail-closed schema policy и продолжения работы человеком или агентом.
- [ ] 1.4 Добавить в инструкцию минимальные `entrypoints.json`, строки очереди и явные команды запуска для Vanessa BDD (`featurePath`) и YAxUnit (`filters`), включая prerequisites и запрет секретов в entrypoint-строках.

## 2. Переиспользуемые исходники тестового контура

- [ ] 2.1 Извлечь в `automation/testing/templates/` очищенную заготовку из Delans Git tree `3a289ff004088f3dece757ea41cc9081ac45d813` (`VATestContour`), безусловно удалить `ОбщегоНазначенияКлиентПереопределяемый` и перенести только отсутствующие по поведению исправления из `DC_BDDWarmServiceGlobal` SHA-256 `4ff1...bb09` и `DC_BDDWarmServiceServerCall` SHA-256 `100f...fa2` без остального `DelansCommon`.
- [ ] 2.2 Подготовить там же обезличенную заготовку `ProjectYAxUnitTests` из Git tree `ca01a015dcb5a310d6b0c602fe41051bc0c7d23c` с подсистемой подключения и минимальной динамической регистрацией без тестов и метаданных Delans.
- [ ] 2.3 Зафиксировать под `automation/testing/vendor/` source-only YAxUnit 25.12 из Git tree `9df324...54e18` и VAExtension 1.29 из `2d8b3b...69462`, лицензии Apache-2.0/BSD-3-Clause, upstream NOTICE/атрибуцию при наличии и `UPSTREAM.json` с release/tag, точными CFE asset SHA-256 и детерминированным source-tree SHA-256.
- [ ] 2.4 Добавить к существующему Python CLI команду `init-test-tooling --project-tests-name <name>` и тонкие Bash/PowerShell-обёртки: preflight всех четырёх целевых каталогов, согласованная замена имени/UUID только для ProjectYAxUnitTests, copytree без сети и полный cleanup при ошибке.

## 3. Vanessa Automation Single

- [ ] 3.1 Добавить `automation/testing/dependencies.json` с Vanessa Automation `1.2.043.28`, URL/asset, ZIP SHA-256 `cd0a...f32a`, EPF SHA-256 `97cf...7a48`, versioned install path и BSD-3-Clause provenance.
- [ ] 3.2 Добавить к Python CLI `install-test-tooling [--archive <local-zip>]` и тонкие обёртки: временная загрузка, проверка ZIP SHA-256, защита от path traversal/links/неожиданных файлов, проверка EPF SHA-256, атомарная публикация, повторное использование совпадающего файла и сохранение других версий.

## 4. Поверхность создаваемого проекта

- [ ] 4.1 Добавить в skeleton создаваемого проекта пустую структуру `analysis/testing/campaigns/.gitkeep` без активной кампании, очередей и результатов.
- [ ] 4.2 Обновить generated-project guidance, runtime support matrix, overlay-манифест и preserve-контракт так, чтобы команды, заготовки и vendor-source распространялись, а материализованные `src/cfe`, состояние кампаний и `.artifacts/testing` не изменялись автоматически.
- [ ] 4.3 Обновить generated docs и примеры профилей: `vanessaSinglePath` указывает на versioned repo-relative `.artifacts/testing` path, а YAxUnit/BDD prerequisites различают init, install, sync и runtime run.

## 5. Проверки без 1С

- [ ] 5.1 Добавить smoke кампании для атомарной инициализации и `use`, дубликатов id, неизвестных schema/полей, symlink/path traversal, приоритета `failed_retry → running → pending`, всех разрешённых и запрещённых переходов, `resultDir`, JSON stdout, исчерпания очереди и selector-ов Vanessa BDD/YAxUnit.
- [ ] 5.2 Проверить Bash/Python путь кампании на Linux и маршрутизацию PowerShell-обёртки существующим fixture-контуром.
- [ ] 5.3 Добавить smoke исходников для отсутствия Delans/известного UUID, целостности внутренних UUID, provenance/source-tree SHA-256, автономной инициализации и нулевых изменений при существующем целевом каталоге.
- [ ] 5.4 Проверить установку EPF через локальный fixture ZIP, повторный запуск, неверный ZIP/хеш, path traversal/link/unexpected-entry, отсутствие частичного файла и сохранение ранее проверенной версии без сетевого smoke-теста.
- [ ] 5.5 Подключить проверки к `make agent-verify`; проверить Copier bootstrap и overlay update с заранее изменёнными `src/cfe`, кампанией и локальным artifact-каталогом.

## 6. Runtime и выпускные gate-ы

- [ ] 6.1 В Delans на target `delans_ut_26_bdd` и `delans_unf_bdd` выполнить `check-cfe-config`, `check-cfe-applicability` и загрузку VATestContour, ProjectYAxUnitTests, YAxUnit и VAExtension.
- [ ] 6.2 На обоих target выполнить минимальные реальные запуски YAxUnit и Vanessa BDD; сохранить команды, версии платформы/конфигурации и run-root evidence в change-local отчёте проверки.
- [ ] 6.3 Запустить `openspec validate add-reusable-testing-campaign --strict --no-interactive`, `make agent-verify`, `make export-context-check` и `git diff --check`.
