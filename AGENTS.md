<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Source Repo Entry Point

- Этот репозиторий является **исходником шаблона**, а не прикладным 1С-решением.
- Начинать обзор и работу нужно с [docs/agent/index.md](docs/agent/index.md): там лежит system of record для структуры, запуска, проверки и review.
- Карта top-level зон и canonical entrypoint-ов: [docs/agent/architecture.md](docs/agent/architecture.md).
- Первый lightweight verification path описан в [docs/agent/verify.md](docs/agent/verify.md) и запускается через `make agent-verify`.
- Для долгих или multi-session задач используйте [docs/exec-plans/README.md](docs/exec-plans/README.md).
- Live context самого шаблона лежит в [automation/context/template-source-project-map.md](automation/context/template-source-project-map.md) и соседних `template-source-*`.
- Skeleton files для generated projects лежат в [automation/context/templates/](automation/context/templates/).
