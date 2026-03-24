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
- `docs/agent/` как стартовый system-of-record слой;
- bootstrap-generated `AGENTS.md` через `openspec init` плюс template overlay.

Generated project не должен воспринимать source-repo artifacts как свой live context.

## Automation Context Split

- `automation/context/template-source-*` описывает именно этот template source repo.
- [automation/context/templates/](../../automation/context/templates/) хранит skeleton files для generated projects.
- Если вы работаете в generated project, создавайте project-specific live context из файлов в `automation/context/templates/`.

## AGENTS Split

- В source repo корневой `AGENTS.md` объясняет, что это template source.
- В generated project `AGENTS.md` создаётся bootstrap-скриптом и получает managed overlay из [scripts/bootstrap/agents-overlay.sh](../../scripts/bootstrap/agents-overlay.sh).
- В обоих случаях первой долговременной точкой навигации остаётся [docs/agent/index.md](index.md).
