# Generated Project-Delta Hotspots Reference

Этот template-scoped reference описывает expected contract для `automation/context/project-delta-hotspots.generated.md`.

## Project-Delta Contract

- generated-derived bridge между project-owned hints и raw inventory;
- refresh-ится только через `./scripts/llm/export-context.sh --write`;
- ссылается на `automation/context/project-delta-hints.json`, `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/runtime-quickstart.md`, `automation/context/hotspots-summary.generated.md`, `automation/context/metadata-index.generated.json`;
- может честно сообщать, что selectors пока не объявлены, и это не делает generated repo невалидным;
- не заменяет curated project-owned domain map и не должен притворяться authoritative business truth.
