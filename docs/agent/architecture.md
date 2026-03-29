# Architecture

## Что это за репозиторий

Это template source repo для 1С-проектов.
Он задаёт contract-first структуру вокруг `OpenSpec -> Beads -> Code`, поставляет versioned launcher-скрипты, примеры runtime profiles и agent-facing tooling.

Это не прикладное 1С-решение и не repository с бизнес-доменом конечного проекта.

## Top-Level Zones

- `src/` — source tree, который template делает доступным generated projects.
- `scripts/` — канонические entrypoint-скрипты для runtime, test, QA, template bootstrap/update и agent automation.
- `env/` — checked-in examples для runtime profiles и local profile conventions.
- `tests/` и `features/` — smoke, fixture, xUnit и BDD слои проверки.
- `automation/` — machine-readable context, reusable prompts и checklists для агентов.
- `.agents/skills/` и `.claude/skills/` — repeatable agent workflows как thin wrappers над repo-owned scripts.
- `.codex/` — project-scoped Codex guidance и optional config examples.
- `docs/` — долговременная документация; `docs/agent/` является agent-facing system of record.
- `openspec/` — contract-first workspace для template source repo.

## Canonical Entrypoints

Runtime and test:

- `./scripts/platform/create-ib.sh`
- `./scripts/platform/dump-src.sh`
- `./scripts/platform/load-src.sh`
- `./scripts/platform/load-diff-src.sh`
- `./scripts/platform/load-task-src.sh`
- `./scripts/platform/update-db.sh`
- `./scripts/platform/diff-src.sh`
- `./scripts/platform/publish-http.sh`
- `./scripts/diag/doctor.sh`
- `./scripts/test/run-xunit.sh`
- `./scripts/test/run-xunit-direct-platform.sh`
- `./scripts/test/build-xunit-epf.sh`
- `./scripts/test/tdd-xunit.sh`
- `./scripts/test/run-bdd.sh`
- `./scripts/test/run-smoke.sh`

Agent and repository checks:

- `./scripts/qa/agent-verify.sh`
- `./scripts/qa/check-agent-docs.sh`
- `./scripts/qa/check-skill-bindings.sh`
- `./scripts/llm/export-context.sh --preview|--check|--write`
- `./scripts/llm/verify-traceability.sh`

Template lifecycle:

- `./scripts/bootstrap/copier-post-copy.sh`
- `./scripts/bootstrap/overlay-post-apply.sh`
- `./scripts/bootstrap/copier-post-update.sh`
- `./scripts/template/check-update.sh`
- `./scripts/template/update-template.sh`
- `./scripts/release/install-source-hooks.sh`
- `./scripts/release/publish-overlay-release.sh --tag vX.Y.Z`

## First-Pass Orientation

- Если нужно понять repo contract, начните с [openspec/project.md](../../openspec/project.md).
- Если нужно быстро проверить repo integrity, используйте [docs/agent/verify.md](verify.md) и `make agent-verify`.
- Если нужно выпустить новый overlay release tag source repo, переходите в [docs/template-release.md](../template-release.md).
- Если задача длинная или кросс-файловая, создайте execution plan в [docs/exec-plans/README.md](../exec-plans/README.md).
- Если длинной задаче нужны bulky supporting artifacts рядом с exec-plan, используйте [docs/work-items/README.md](../work-items/README.md).
