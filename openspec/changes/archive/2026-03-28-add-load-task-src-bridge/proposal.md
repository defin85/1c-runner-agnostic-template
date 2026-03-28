# Change: добавить repo-owned мостик `task commits -> partial load-src`

## Why

Шаблон уже поставляет `scripts/platform/load-diff-src.sh`, но этот wrapper покрывает только незакомиченные изменения текущего worktree. В реальном agent-assisted workflow это недостаточно: агент и человек часто коммитят по ходу работы, а затем хотят загрузить в ИБ именно изменения конкретной задачи, даже если рабочее дерево уже чистое.

Сейчас такой сценарий требует вручную восстанавливать список файлов из commit history, range или task context, а потом отдельно передавать его в `load-src --files`. Это создаёт ad hoc shell snippets, смешивает unrelated commits и делает partial import зависимым от дисциплины оператора, а не от repo-owned contract.

## What Changes

- Добавить новый repo-owned wrapper `scripts/platform/load-task-src.sh`, который строит explicit selection файлов `src/cf` из уже закомиченных изменений и делегирует actual import в существующий `scripts/platform/load-src.sh --files`.
- Зафиксировать canonical selectors для task-scoped loading:
  - `--bead <id>` через commit trailer `Bead:`
  - `--work-item <id>` через commit trailer `Work-Item:`
  - `--range <revset>` как явный fallback для legacy history и одноразовых случаев
- Зафиксировать, что wrapper использует repo-owned commit metadata contract и git history entrypoint-ы, а не parsing patch-output и не `git notes`.
- Добавить repo-owned helper/validation surface для canonical trailers `Bead:` и `Work-Item:`, чтобы task-scoped selection не опирался только на ручную дисциплину commit message.
- Зафиксировать machine-readable artifact contract wrapper-а: он должен писать собственный `summary.json` и явно отражать selector, selected commits, selected files, ignored/deleted paths и delegated `load-src` run.
- Обновить template-managed agent workflows, skill packaging, docs и smoke coverage для нового task-scoped bridge.

## Impact

- Affected specs:
  - `agent-runtime-toolkit`
  - `ibcmd-capability-drivers`
  - `project-scoped-skills`
- Affected code:
  - `scripts/platform/`
  - `scripts/git/`
  - `scripts/lib/`
  - `.agents/skills/`
  - `.claude/skills/`
  - `tests/smoke/`
  - `README.md`
  - `docs/agent/architecture.md`
  - `docs/agent/generated-project-index.md`
  - `env/README.md`
