# Source Vs Generated

## Source Repo

Текущий репозиторий является исходником шаблона.
Здесь живут:

- OpenSpec specs и changes самого шаблона;
- bootstrap/update hooks;
- smoke tests template delivery;
- truthful live context этого template source repo;
- docs про устройство шаблона.

## Generated Project

Generated project получает:

- launcher scripts;
- env examples;
- CI workflow;
- `.agents/skills/` и `.claude/skills/`;
- `docs/agent/` как template-managed стартовый слой, включая [generated-project-index.md](generated-project-index.md) и [generated-project-verification.md](generated-project-verification.md);
- project-owned `docs/work-items/` как companion workspace для supporting artifacts длинных задач;
- bootstrap-generated `AGENTS.md` через `openspec init` плюс template overlay.

Generated project не должен воспринимать source-repo artifacts как свой live context.

## Ownership Classes

- `template-managed`: reusable scripts, shared docs, shared skills, CI contours, managed blocks, `.template-overlay-version`.
- `seed-once / project-owned`: root `README.md`, `openspec/project.md`, `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/runtime-quickstart.md`, `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md`, `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`.
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`.
- `local-private`: local runtime profiles, secrets, machine-specific Codex/MCP config.

## Automation Context Split

- `automation/context/template-source-*` описывает именно этот template source repo.
- [automation/context/templates/](../../automation/context/templates/) хранит skeleton files для generated projects.
- Если вы работаете в generated project, держите curated truth в `automation/context/project-map.md`, `docs/agent/architecture-map.md` и `docs/agent/runtime-quickstart.md`, checked-in runtime truth в `automation/context/runtime-support-matrix.md` / `.json`, living progress в `docs/exec-plans/`, task-local supporting artifacts в `docs/work-items/`, а generated-derived inventory refresh-ите через `./scripts/llm/export-context.sh --write`.

## AGENTS Split

- В source repo корневой `AGENTS.md` объясняет, что это template source.
- В generated project `AGENTS.md` создаётся bootstrap-скриптом и получает managed overlay из [scripts/bootstrap/agents-overlay.sh](../../scripts/bootstrap/agents-overlay.sh).
- В source repo первой долговременной точкой навигации остаётся [docs/agent/index.md](index.md).
- В generated project primary onboarding route должен начинаться с [generated-project-index.md](generated-project-index.md), а template maintenance path должен оставаться отдельным.
- Generated-project closeout contract должен различать `local-only` и `remote-backed` handoff, а не навязывать безусловный push-only путь.
