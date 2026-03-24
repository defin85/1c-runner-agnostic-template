---
name: repo-agent-verify
description: Запускает lightweight baseline verification для docs, OpenSpec, skills и live context этого репозитория.
metadata:
  short-description: Baseline verify для agent-facing изменений.
---

# Agent Skill: Repo Agent Verify

Repo script: `./scripts/qa/agent-verify.sh`

## Use When

- Вы меняли `AGENTS.md`, `docs/agent/`, `.agents/skills/`, `.codex/` или `automation/context/`.
- Нужно быстро проверить repo/doc/tooling surface без 1С runtime и без BSL-heavy contour.

## Usage

```bash
./scripts/qa/agent-verify.sh
make agent-verify
```

## Rules

- Это baseline contour, а не замена fixture/runtime smoke.
- Если baseline прошёл, а change затрагивает template delivery, переходите к `tests/smoke/bootstrap-agents-overlay.sh` и `tests/smoke/copier-update-ready.sh`.
