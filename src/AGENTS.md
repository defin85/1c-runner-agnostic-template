# Source Tree Routing

`src/` хранит только deployable исходники.

- В generated repo сначала сверяйтесь с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md), затем переходите к `automation/context/project-map.md` и `automation/context/metadata-index.generated.json`, чтобы сузить поиск по `src/`.
- В template source repo содержимое `src/` остаётся scaffold/skeleton surface и не является business-domain truth реального проекта.
- Не переносите в `src/` execution plans, traceability, review notes или template-maintenance инструкции.
