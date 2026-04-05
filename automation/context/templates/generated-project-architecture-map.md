# Generated Architecture Map Starter Reference

Этот template-scoped reference описывает expected contract для project-owned `docs/agent/architecture-map.md`.

## Architecture Map Contract

- остаётся project-owned прикладной картой, а не template-managed manual;
- фиксирует repo-derived snapshot, если current tree уже даёт high-signal факты;
- отвечает на вопрос “где менять X?” через representative change scenarios;
- связывает сценарии с likely paths, metadata objects и nearby runbooks/tests;
- ссылается на `automation/context/project-map.md`, `automation/context/recommended-skills.generated.md`, `automation/context/project-delta-hotspots.generated.md`, `automation/context/hotspots-summary.generated.md`, `automation/context/metadata-index.generated.json`, `docs/agent/runtime-quickstart.md`;
- остаётся достаточно короткой, чтобы сузить поиск до 1-2 `rg` проходов, а не заменить весь raw inventory.
