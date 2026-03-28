# Change: добавить repo-owned мостик `diff -> partial load-src`

## Why

Шаблон уже поставляет отдельные entrypoint-ы `scripts/platform/diff-src.sh` и `scripts/platform/load-src.sh`, а `load-src` при `driver=ibcmd` уже умеет partial import через `--files`. Но reusable repo-owned мостика между этими шагами пока нет.

Из-за этого оператор или агент вынужден вручную превращать VCS diff в список относительных файлов `src/cf`, помнить про фильтрацию удалений и untracked файлов, а затем отдельно вызывать `load-src --files`. Это не project-specific проблема одного generated repo, а пробел именно template-managed productivity surface.

## What Changes

- Добавить новый repo-owned wrapper `scripts/platform/load-diff-src.sh`, который строит explicit selection файлов из git-backed diff и делегирует фактическую загрузку в существующий `scripts/platform/load-src.sh --files`.
- Зафиксировать, что wrapper не парсит patch-output `diff-src.sh` и не зависит от произвольного `capabilities.diffSrc.command`; он сам вычисляет список changed files из git-backed source tree.
- Зафиксировать fail-closed поведение, если после фильтрации не осталось ни одного подходящего файла внутри `src/cf`.
- Зафиксировать machine-readable artifact contract wrapper-а: он должен писать собственный `summary.json` и явно отражать delegated `load-src` run.
- Добавить template-managed agent workflow/skill для намерения "загрузить diff в ИБ".
- Обновить template-managed docs и smoke coverage для нового мостика.

## Impact

- Affected specs:
  - `agent-runtime-toolkit`
  - `ibcmd-capability-drivers`
  - `project-scoped-skills`
- Affected code:
  - `scripts/platform/`
  - `scripts/lib/`
  - `.agents/skills/`
  - `.claude/skills/`
  - `tests/smoke/`
  - `README.md`
  - `docs/agent/architecture.md`
  - `env/README.md`
