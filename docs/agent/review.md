# Review

## Основные критерии

При review в этом репозитории сначала проверяйте:

- не появилось ли дублирование runtime logic вне `scripts/`;
- не потерялась ли связка `Requirement -> Code -> Test`;
- не стали ли agent-facing docs противоречить реальному repo contract;
- не добавились ли machine-specific или secret-bearing артефакты в template;
- не ухудшился ли versioned overlay maintenance path.

## Для Doc And Agent-Tooling Changes

Если change касается `AGENTS.md`, `docs/agent/`, `.agents/skills/`, `.codex/` или `automation/context/`, проверьте:

- есть ли один очевидный entrypoint для нового агента;
- не появились ли placeholders в live context;
- нет ли line-specific links в durable docs;
- остаются ли skills thin wrappers, а не вторым источником логики;
- проходит ли `make agent-verify`.

## Для Template Delivery Changes

Если change затрагивает bootstrap/update/template delivery, проверьте:

- `tests/smoke/bootstrap-agents-overlay.sh`;
- `tests/smoke/copier-update-ready.sh`;
- отсутствие source-repo-only артефактов там, где generated project не должен их получать.
