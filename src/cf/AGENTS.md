# Main Configuration Routing

`src/cf/` хранит основную конфигурацию и обычно даёт самый высокий объём поиска в generated repo.

- Сначала откройте `docs/agent/architecture-map.md`, если нужен project-owned ответ на вопрос “где менять X?”.
- Для короткого runtime ответа держите рядом `docs/agent/runtime-quickstart.md` и `automation/context/runtime-support-matrix.md`.
- Для summary-first narrowing search используйте `automation/context/hotspots-summary.generated.md`; raw inventory `automation/context/metadata-index.generated.json` открывайте уже после этого.
- Для локального routing по зонам сначала смотрите `src/cf/CommonModules`, `src/cf/ScheduledJobs`, `src/cf/HTTPServices`, `src/cf/WebServices`, `src/cf/DataProcessors`, `src/cf/Subsystems`.
- Если проект добавит ещё более локальные `AGENTS.md` ниже по дереву, приоритет у ближайшего файла.
- Не переносите сюда execution plans, review notes или template-maintenance инструкции.
