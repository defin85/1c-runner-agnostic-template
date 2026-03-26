# Документация

Сюда складывается долговременная документация проекта:

- ADR
- архитектурные схемы
- описание контуров запуска
- эксплуатационные заметки
- решения по интеграциям
- agent-facing system of record в [docs/agent/](agent/)
- versioned execution plans в [docs/exec-plans/](exec-plans/)

В этот каталог не стоит класть активные change-spec файлы. Для них есть `openspec/changes/`.

Если вы новый агент:

- в template source repo начните с [docs/agent/index.md](agent/index.md);
- в generated repo начните с [docs/agent/generated-project-index.md](agent/generated-project-index.md), затем откройте `automation/context/project-map.md` и `automation/context/hotspots-summary.generated.md`;
- isolated template refresh path всегда живёт отдельно в [docs/template-maintenance.md](template-maintenance.md).
- source template release path для maintainer-а живёт отдельно в [docs/template-release.md](template-release.md).
