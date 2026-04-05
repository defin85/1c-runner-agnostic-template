# Script Routing

Этот каталог содержит canonical entrypoints и shared automation boundaries.

- Для generated repo сначала откройте [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md), затем сверяйтесь с `automation/context/project-map.md` и `automation/context/hotspots-summary.generated.md`.
- Read-only first screen для generated repo даёт `make codex-onboard`.
- `automation/context/recommended-skills.generated.md` даёт compact project-aware skill routing, а `make imported-skills-readiness` проверяет executable imported compatibility surface.
- Runtime semantics и sanctioned checked-in presets ищите в [env/README.md](../env/README.md) и `automation/context/runtime-profile-policy.json`.
- Checked-in runtime truth ищите в `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
- `scripts/llm/export-context.sh` отвечает за privacy-safe generated context: `source-tree.generated.txt`, `metadata-index.generated.json`, `hotspots-summary.generated.md`.
- `scripts/qa/check-agent-docs.sh` и smoke-контракты должны fail-closed ловить source-centric drift, placeholder verification и stale generated artifacts.
- Не превращайте `scripts/` в место для ad-hoc заметок, планов или project-owned domain truth.
