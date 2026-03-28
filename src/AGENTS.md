# Source Tree Routing

`src/` хранит только deployable исходники.

- В generated repo сначала сверяйтесь с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md), затем переходите к `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/runtime-quickstart.md`, `automation/context/project-delta-hotspots.generated.md`, `automation/context/hotspots-summary.generated.md` и только потом к `automation/context/metadata-index.generated.json`, чтобы сузить поиск по `src/`.
- Для dense main configuration tree держите routing выше deployable `src/cf`: первый проход обычно начинается с `src/cf/CommonModules`, `src/cf/ScheduledJobs`, `src/cf/HTTPServices`, `src/cf/WebServices`, `src/cf/DataProcessors` и `src/cf/Subsystems`.
- В template source repo содержимое `src/` остаётся scaffold/skeleton surface и не является business-domain truth реального проекта.
- Не переносите в `src/` execution plans, traceability, review notes или template-maintenance инструкции.
- Не размещайте `AGENTS.md`, `README.md` и другие routing-only markdown artifacts внутри deployable `src/cf`.
