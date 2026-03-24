# Change: добавить Codex-friendly agent surface для template source repo

## Why

Текущий template source repo уже содержит полезные runtime entrypoint-ы, smoke-проверки и OpenSpec workflow, но новый Codex-агент получает этот контекст слишком медленно.

Основные проблемы сейчас такие:

- корневой `AGENTS.md` фактически содержит только managed OpenSpec block и не объясняет, что это template source repo;
- agent-facing documentation распределена между `README.md`, `openspec/project.md`, `env/README.md`, `tests/README.md`, `automation/*` и CI без одного system-of-record entrypoint;
- live `automation/context/*` содержит template placeholders и тексты вида "обновите после создания реального проекта", что делает машинный контекст недостоверным для самого source repo;
- у репозитория нет явного lightweight onboarding/verification path для агента; самый заметный target `make qa` тянет более тяжёлый BSL contour;
- Claude-specific packaging выражена лучше, чем Codex-specific reuse: есть `.claude/skills/*`, но нет repo-local `.agents/skills/*` и нет понятной `.codex` guidance surface;
- static CI пока не проверяет целостность и свежесть agent-facing docs/context.

В результате Codex тратит лишние ходы на discovery, verification и reconcile между несколькими частично авторитетными документами.

## What Changes

- добавить новую capability `repository-agent-guidance`, которая зафиксирует:
  - concise root agent entrypoint;
  - docs index и минимальный набор authoritative runbook-ов;
  - truthful live automation context для template source repo;
  - lightweight agent verification path;
  - versioned execution-plan area для long-running agent work;
- расширить `project-scoped-skills`, чтобы template source repo и generated projects имели Codex-discoverable `.agents/skills/` и единый intent-to-capability mapping, а vendor-specific wrappers оставались thin facades;
- расширить `template-ci-contours`, чтобы static contour валидировал freshness/integrity agent-facing docs, context и skills без реального 1С runtime;
- зафиксировать durable-doc linking policy: в system-of-record документации использовать file/section links как primary navigation, а line-specific links оставить для audit/review/traceability артефактов.

## Out Of Scope

- Рефакторинг runtime adapter layer или launcher scripts, не связанный напрямую с agent onboarding.
- Изменение business/runtime behavior generated projects.
- Введение обязательных machine-specific MCP зависимостей в checked-in `.codex/config.toml`.
- Замена существующих `.claude/skills/*` на vendor-locked Codex-only flow.

## Impact

- Affected specs:
  - `repository-agent-guidance`
  - `project-scoped-skills`
  - `template-ci-contours`
- Affected code:
  - `AGENTS.md`
  - `README.md`
  - `docs/README.md`
  - `docs/agent/*`
  - `docs/exec-plans/*`
  - `automation/context/*`
  - `automation/prompts/*` (если потребуется индекс/шаблон для execution plans)
  - `.codex/config.toml`
  - `.codex/README.md`
  - `.agents/skills/*`
  - `.claude/skills/*`
  - `.claude/skills/README.md`
  - `Makefile`
  - `scripts/llm/export-context.sh`
  - `scripts/qa/check-skill-bindings.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `.github/workflows/ci.yml`
  - `tests/smoke/bootstrap-agents-overlay.sh`
  - `tests/smoke/copier-update-ready.sh`
