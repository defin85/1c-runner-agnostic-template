# Generated Operator-Local Runbook Starter Reference

Этот template-scoped reference описывает expected contract для project-owned `docs/agent/operator-local-runbook.md`.

## Runbook Contract

- отвечает на вопрос “реально ли этот contour runnable здесь и чего не хватает?”;
- остаётся project-owned bridge для `operator-local` и `provisioned` contour-ов;
- ссылается на `automation/context/runtime-support-matrix.md`, `.json`, `docs/agent/runtime-quickstart.md`, `env/README.md`, `docs/agent/generated-project-verification.md`;
- перечисляет canonical `operator-local` contour-ы `doctor`, `load-diff-src` и `load-task-src`;
- фиксирует canonical entrypoint-ы `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run`, `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` и `./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run`;
- фиксирует preflight checks, canonical entrypoint-ы, env/profile provenance и expected fail-closed states;
- не делает ignored local-private profile shared baseline truth.
