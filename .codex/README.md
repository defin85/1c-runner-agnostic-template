# Codex Repo Guide

Используйте этот каталог как project-scoped companion к root `AGENTS.md`.

## С чего начинать

- Доверьте репозиторий, чтобы Codex подхватил `.codex/config.toml`.
- В source repo начните с [docs/agent/index.md](../docs/agent/index.md).
- В generated project начните с [docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md).
- В generated project для read-only первого экрана используйте `make codex-onboard`.
- Для первого прогона используйте `make agent-verify`.
- Для generated project используйте [docs/agent/codex-workflows.md](../docs/agent/codex-workflows.md) как canonical workflow guide после первого router step.
- Для operator-local runtime решений в generated project держите project-owned bridge в `docs/agent/operator-local-runbook.md`.
- Для generated project дополнительно сверяйтесь с `automation/context/runtime-support-matrix.md`, `docs/agent/runtime-quickstart.md`, [env/README.md](../env/README.md), [docs/agent/review.md](../docs/agent/review.md), [.agents/skills/README.md](../.agents/skills/README.md), [docs/exec-plans/README.md](../docs/exec-plans/README.md), [docs/exec-plans/TEMPLATE.md](../docs/exec-plans/TEMPLATE.md) и [docs/work-items/README.md](../docs/work-items/README.md).
- Repeatable workflows лежат в [.agents/skills/README.md](../.agents/skills/README.md).

## Closeout

- `local-only`: если writable remote отсутствует или handoff по договорённости локальный, не изобретайте обязательный push; сдайте локальный diff и verification state.
- `remote-backed`: если проект работает через remote, sync и push идут только после локально зелёных quality gates.

## Optional MCP And Config

- `config.toml` здесь intentionally host-safe by default: checked-in MCP examples закомментированы.
- Если включаете локальные MCP servers, адаптируйте пути и env values под свою машину.
- Не делайте machine-specific MCP paths обязательными для команды или CI.
