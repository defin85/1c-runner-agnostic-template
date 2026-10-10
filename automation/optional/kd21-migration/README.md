# Заготовка модуля `kd21-migration`

Модуль добавляет в проект рабочий контур правил обмена формата КД 2.01. Включается командой
`make optional-module-init MODULE=kd21-migration` (Windows: `./make.ps1 optional-module-init kd21-migration`).

Файлы из `files/` копируются в проект по тем же относительным путям:

- `migration/kd21/` — примеры профиля и сценария `technical-workbench`, матрица файлов выпуска, ожидаемый результат, демонстрационные структуры метаданных, обработка выгрузки структуры `metadata-exporter`, заготовка команды загрузки правил и заготовка раздела `## Влияние на миграцию`;
- `docs/agent/kd21-rules-workbench-runbook.md` — регламент контура;
- `.agents/skills/1c-prepare-manual-migration-bases/` — навык подготовки баз ручной проверки (дополнительно копируется в `.claude/skills/`).

Исполнитель `scripts/migration/kd-rules-cycle` и ядро компилятора `scripts/migration/kd_xml_compiler/` остаются template-managed и обновляются через `template-update`. Прикладные правила обмена в заготовку не входят: проект подключает их через `compiler.rulesProvider` сценария.
