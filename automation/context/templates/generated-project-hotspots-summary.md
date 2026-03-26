# Generated Hotspots Summary Reference

Этот template-scoped reference описывает expected contract для `automation/context/hotspots-summary.generated.md`.

## Summary Contract

- generated-derived summary-first карта для первого часа работы агента;
- ссылается на `automation/context/project-map.md` как curated truth;
- ссылается на `automation/context/runtime-support-matrix.md` как checked-in runtime truth;
- ссылается на `automation/context/metadata-index.generated.json` как raw inventory;
- содержит identity, freshness metadata, high-signal counts и task-to-path routing hints;
- refresh-ится через `./scripts/llm/export-context.sh --write`.
