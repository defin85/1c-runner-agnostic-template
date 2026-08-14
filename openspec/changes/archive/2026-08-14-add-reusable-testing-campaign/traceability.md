# Traceability

## reusable-testing-campaign

- Переносимая кампания для Vanessa BDD и YAxUnit
  - Code: `scripts/python/testing_campaign.py`, thin Bash/PowerShell wrappers, existing BDD/YAxUnit entrypoints
  - Docs: `docs/testing/campaigns.md`, `analysis/testing/README.md`
  - Tests: `tests/smoke/testing-campaign-contract.sh`, `tests/smoke/copier-update-ready.sh`

## reusable-testing-tooling

- Переиспользуемый 1С-контур Vanessa и каркас проектных тестов YAxUnit
  - Code: `automation/testing/templates/`, `init-test-tooling`
  - Tests: отсутствие Delans/конфигурационных UUID, согласованность UUID, защита существующих каталогов
- Закреплённые upstream-source YAxUnit и VAExtension
  - Code: `automation/testing/vendor/`, provenance и лицензии
  - Tests: source inventory, версии, SHA-256 и автономное копирование
- Воспроизводимая установка Vanessa Automation Single
  - Code: `automation/testing/dependencies.json`, `install-test-tooling`, `.artifacts/testing/vanessa/<version>/`
  - Tests: fixture ZIP, SHA-256, повторный запуск и сохранение ранее проверенного EPF при ошибке
- Runtime-совместимость
  - Code: существующие `check-cfe-*`, `load-cfe`, YAxUnit и BDD entrypoint-ы
  - Tests: provisioned-runtime evidence для четырёх расширений и двух минимальных запусков
