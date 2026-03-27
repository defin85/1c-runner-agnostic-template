## Context

В шаблоне уже есть два соседних, но разных контура:

- `scripts/platform/load-diff-src.sh` для незакомиченного git-backed diff;
- `scripts/platform/load-src.sh --files` для явного partial import через `ibcmd`.

Проблема возникает после коммитов. Как только task changes попали в history и worktree очистился, current `load-diff-src` перестаёт быть полезным. При этом agent-assisted workflow сам по себе провоцирует промежуточные коммиты: агент часто коммитит после каждого закрытого куска работы, а затем оператору нужен deterministic способ загрузить в ИБ именно изменения этой задачи, а не весь branch или весь локальный diff.

## Goals

- Дать source repo и generated project-ам repo-owned wrapper для `task-scoped commits -> partial load-src`.
- Сохранить `load-src` единственной точкой actual runtime import semantics.
- Сделать commit selection deterministic и пригодным для machine-readable automation.
- Уменьшить зависимость от ручного составления списка файлов после нескольких коммитов.

## Non-Goals

- Не менять семантику существующего `load-src`.
- Не перегружать `load-diff-src` committed-history режимами.
- Не парсить patch-output `diff-src.sh`.
- Не использовать `git notes` как canonical metadata contract.
- Не угадывать task scope по branch name или по free-form commit subject.
- Не делать автоматический `update-db` после partial import.

## Decisions

### 1. Отдельный wrapper, а не расширение `load-diff-src.sh`

Новый workflow будет жить в отдельном `scripts/platform/load-task-src.sh`.

Почему:

- `load-diff-src` остаётся простым контуром для текущего worktree;
- committed-history selection получает собственный CLI и собственный debug surface;
- проще различать два намерения:
  - "загрузи незакомиченный diff"
  - "загрузи уже закомиченные изменения задачи"

### 2. Canonical selectors: trailers first, range second

Primary contract:

- `--bead <id>` ищет commits с trailer `Bead: <id>`
- `--work-item <id>` ищет commits с trailer `Work-Item: <id>`

Fallback contract:

- `--range <revset>` позволяет явно задать commit range для legacy history или единичного recovery-сценария

Почему именно так:

- trailers остаются внутри commit object и переживают обычный `push/pull`;
- `Bead` хорошо подходит для узкой execution unit;
- `Work-Item` покрывает более широкий task scope;
- `range` остаётся полезным escape hatch, но не должен быть единственным основным path.

### 3. Repo-owned helper/validation surface для commit trailers

Шаблон должен поставлять repo-owned helper или hook-installer, который помогает нормализовать `Bead:` и `Work-Item:` trailers для task-scoped workflow.

Решение:

- helper/hook path остаётся versioned и документированным;
- фактическая установка hook-а должна быть явным opt-in действием, а не скрытой пост-обновлялкой template overlay;
- validation surface должен уметь fail-closed сигнализировать, что commit history не содержит нужных canonical markers.

### 4. Wrapper извлекает metadata из git history, а file set из `diff-tree`

Wrapper не должен читать произвольный patch-text и не должен зависеть от `git notes`.

Следствие:

- trailers нужно разбирать через `git interpret-trailers` или эквивалентный repo-owned parser;
- список файлов нужно собирать через `git rev-list`/`git log` + `git diff-tree --name-status`;
- selection logic остаётся deterministic и testable.

### 5. Actual import остаётся за `load-src.sh --files`

Новый wrapper не пишет собственный 1С runtime argv и не дублирует `ibcmd`/adapter logic.

Следствие:

- runtime import semantics остаётся в одном месте;
- `load-task-src` отвечает только за commit discovery, path filtering, summary и delegation;
- существующий contract partial import через `load-src` остаётся source of truth.

### 6. Fail-closed policy на пустой или непригодный selection

Wrapper должен завершаться non-zero до запуска `load-src`, если:

- selector не нашёл ни одного commit;
- после фильтрации не осталось ни одного eligible path внутри `src/cf`;
- selection состоит только из удалённых или несуществующих paths;
- пользователь передал взаимоисключающие selector flags.

При этом wrapper должен отражать ignored/deleted paths и selector context в `summary.json`.

## Risks / Trade-offs

- Commit trailer contract добавляет процессную дисциплину, но без него task-scoped loading останется эвристикой.
- `--range` удобен, но может захватывать unrelated commits; поэтому он остаётся fallback, а не canonical selector.
- Git hooks не versioned самим Git, поэтому repo-owned hook installer должен быть opt-in и хорошо документирован.

## Open Questions

- Нужно ли в v1 отдельно маркировать `Configuration.xml` и другие root metadata как `dangerous_paths` в summary, или достаточно общего selected/ignored breakdown.
- Нужен ли v1-флаг для объединения committed task selection с текущим незакомиченным diff, или это лучше оставить будущему change.
