## Context

В шаблоне уже есть две половины нужного workflow:

- `scripts/platform/diff-src.sh` как человеко-ориентированный diff entrypoint;
- `scripts/platform/load-src.sh --files` как explicit partial import path для `ibcmd`.

Проблема в том, что между ними нет stable repo-owned bridge. Если просто советовать пользователю "возьми `git diff --name-only` и передай его в `load-src --files`", то логика нормализации, фильтрации и fail-closed policy оказывается размазана по ad hoc shell snippets и перестаёт быть updateable через template release.

## Goals

- Дать generated project-ам и source repo reusable wrapper для `diff -> partial load-src`.
- Переиспользовать существующий `load-src` как единственную точку actual runtime import.
- Сохранить machine-readable artifacts и явные guardrails.

## Non-Goals

- Не менять семантику существующего `load-src`.
- Не парсить patch-output `diff-src.sh` или произвольный `capabilities.diffSrc.command`.
- Не добавлять автоматический `update-db` после загрузки diff.
- Не строить semantic safety-engine, который пытается угадывать "опасность" отдельных metadata files.

## Decisions

### 1. Отдельный wrapper, а не расширение `load-src.sh`

Новый workflow будет жить в отдельном `scripts/platform/load-diff-src.sh`.

Почему:

- `load-src` остаётся простым runtime entrypoint-ом: full import или explicit `--files`.
- diff-derived selection становится отдельной ответственностью с собственным summary/debug surface.
- проще документировать и тестировать fail-closed случаи `нет файлов`, `удаления`, `вне source tree`.

### 2. Wrapper сам вычисляет file list из git-backed source tree

Wrapper не должен зависеть от текстового вывода `diff-src.sh`, потому что:

- `diff-src.sh` ориентирован на human-readable diff;
- `capabilities.diffSrc.command` может быть profile-defined и не обязана быть machine-readable;
- parsing patch-output создаёт хрупкую связность между двумя scripts.

Следствие: wrapper использует `git diff --name-only` и сопутствующие git entrypoint-ы напрямую, после чего нормализует пути относительно `src/cf`.

### 3. Wrapper делегирует actual import в `load-src.sh --files`

Wrapper не пишет собственный 1С runtime argv и не дублирует `ibcmd`/adapter logic.

Следствие:

- весь runtime import остаётся за `load-src`;
- `load-diff-src` отвечает только за discovery, filtering, summary и delegation;
- текущий capability contract `Partial Configuration Import Through Load-Src` остаётся source of truth для actual import semantics.

### 4. Fail-closed при пустом selection после фильтрации

Если diff содержит только:

- удаления,
- пути вне `src/cf`,
- пустой результат после нормализации,

wrapper обязан завершаться non-zero до запуска `load-src`.

Это исключает ложнозелёный сценарий "команда отработала, но ничего не загрузила".

### 5. Machine-readable summary wrapper-а

`load-diff-src.sh` должен писать свой `summary.json`, где явно отражены:

- git mode/range, по которому строился selection;
- итоговый список selected files;
- ignored paths и причина фильтрации;
- delegated run root/summary для реального `load-src`.

Это позволяет агенту отлаживать bridge отдельно от inner runtime import.

## Open Questions

- Нужен ли v1 support для staged-only режима (`--cached`) наряду с default worktree mode.
- Нужно ли в v1 включать untracked файлы только для worktree mode, или всегда требовать git-visible paths.
