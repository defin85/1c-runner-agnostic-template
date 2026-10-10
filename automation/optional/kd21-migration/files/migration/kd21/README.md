# Рабочий контур правил КД 2.01

Каталог создан командой `make optional-module-init MODULE=kd21-migration` и принадлежит проекту: `template-update` его не меняет.

| Путь | Назначение |
| --- | --- |
| `profiles/local.example.json` | Пример профиля. Скопируйте в `profiles/local.json` и замените имена баз, снимков и команд своими. |
| `scenarios/technical-workbench/` | Технический сценарий: пустые правила, которые платформа должна принять. `structures/` содержит демонстрационные структуры; замените их выгрузкой своих конфигураций. |
| `metadata-exporter/` | Исходники внешней обработки выгрузки структуры метаданных в XML формата КД. |
| `bin/load_rules.py` | Не поставляется: создайте команду стадии `load`, которая загружает выпуск в расходуемую базу штатной обработкой и пишет `{"status": "passed"}` в `KD_RULES_CYCLE_RESULT_FILE`. Пока файла нет, `doctor` завершается ошибкой `command file not found`. |
| `templates/migration-impact-section.md` | Заготовка раздела `## Влияние на миграцию` для proposal прикладных changes. |

Регламент: [docs/agent/kd21-rules-workbench-runbook.md](../../docs/agent/kd21-rules-workbench-runbook.md).
