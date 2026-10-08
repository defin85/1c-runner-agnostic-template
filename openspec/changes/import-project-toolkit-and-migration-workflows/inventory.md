# Инвентарь сверки template-managed файлов проекта-источника

Сверка: проект `tn-bp30-sdd` коммит `099860613`, база `v0.3.36`, HEAD шаблона `755dfd2`.

Инвентарь выполняет задачу 0.2 из `tasks.md`. Для каждого пути взят diff файла проекта на коммите `099860613` относительно тега `v0.3.36` шаблона и сопоставлен с тем, что шаблон изменил после `v0.3.36` до HEAD `755dfd2`. Набор путей: 181 template-managed файл, отличающийся от `v0.3.36`, и 70 путей, которые проект убрал из своего `template-managed-paths.txt`; всего 251.

## Значение решений

- `перенести` — общая правка; переносится в шаблон без изменения смысла.
- `обобщить` — правка общая по сути, но содержит проектные имена или должна быть переписана под текущий HEAD шаблона (например, в Python-runtime вместо удалённой shell-логики).
- `оставить в проекте` — правка проектная; в шаблон не переносится. В причине указана project-owned точка расширения, если она нужна.
- `уже есть` — HEAD шаблона уже содержит эквивалент.
- `вывести` — путь выводимого импортированного редактора метаданных (решение Р6).

Важный контекст HEAD шаблона: после `v0.3.36` сценарии `scripts/platform/*.sh` (кроме `v8unpack.sh`) и `scripts/diag/doctor.sh` стали тонкими вызовами `run-python.sh`, а основная логика переехала в Python-runtime. Поэтому shell-правки проекта в `scripts/lib/*.sh` и `scripts/platform/*.sh` получают решение `обобщить`: их нужно реализовать в Python-модулях HEAD, а не копировать shell-код.

## Сводка

| Решение | Число путей |
|---|---|
| `перенести` | 13 |
| `обобщить` | 112 |
| `оставить в проекте` | 5 |
| `уже есть` | 54 |
| `вывести` | 67 |
| Всего | 251 |

По виду: managed — 181, убран из списка проекта — 70.

## Таблица

| Путь | Вид | Решение | Причина | Задача |
|---|---|---|---|---|
| `.agents/skills/1c-load-src/SKILL.md` | managed | обобщить | Добавлено правило частичной загрузки нового объекта вместе с родителем; пример `stage_overlay` и «пакет БП20» проектные, их нужно убрать. | 3.3 |
| `.agents/skills/1c-run-bdd/SKILL.md` | managed | перенести | Пример `features/vanessa/example.feature` заменён на `features/examples/tdd-starter.feature`; в HEAD шаблона есть только второй файл, так что это исправление битой ссылки. | 3.3 |
| `.agents/skills/README.md` | managed | обобщить | Добавлены `repo-agent-verify`, `1c-observe-run`, `1c-run-client`, `metadata-*` и раздел навыков площадки TNL (`tnl-citrix-xpra`, сервер `VDC01-…`); README генерирует `imported_skills.py`, поэтому общие строки добавить в генератор, а список проектных навыков вынести в project-owned раздел. | 7.1 |
| `.agents/skills/cfe-borrow/SKILL.md` | убран из списка | вывести | Импортированный редактор `cfe-borrow` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/db-create/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-dump-cf/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-dump-xml/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-load-cf/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-load-git/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-load-xml/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/db-run/SKILL.md` | managed | обобщить | Сгенерированный навык: `db-run` предпочитает `1c-run-client` и проксирует `--profile`/`screenshot\|status\|stop\|key\|click` в `run-client.sh`, плюс ссылка на `1c-observe-run`; переносится через генератор `imported_skills.py`. | 1.5 |
| `.agents/skills/db-update/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/epf-build/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/epf-dump/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/erf-build/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/erf-dump/SKILL.md` | managed | обобщить | Сгенерированный навык: профильный вызов через ibcmd без перехода на Designer, параметры `--profile/--target/--run-root`, раздел о доказательствах запуска; переносится через `imported_skills.py`. | 3.3 |
| `.agents/skills/form-add/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-add` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/form-compile/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-compile` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/form-edit/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-edit` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/form-info/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-info` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/form-remove/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-remove` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/form-validate/SKILL.md` | убран из списка | вывести | Импортированный редактор `form-validate` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/meta-compile/SKILL.md` | убран из списка | вывести | Импортированный редактор `meta-compile` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/meta-edit/SKILL.md` | убран из списка | вывести | Импортированный редактор `meta-edit` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/meta-info/SKILL.md` | убран из списка | вывести | Импортированный редактор `meta-info` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/meta-remove/SKILL.md` | убран из списка | вывести | Импортированный редактор `meta-remove` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.agents/skills/meta-validate/SKILL.md` | убран из списка | вывести | Импортированный редактор `meta-validate` выводится по Р6 в пользу CLI `metadata`; проект уже удалил навык. | 2.7 |
| `.claude/skills/1c-create-ib/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-create-ib/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-diff-src/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-diff-src/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-doctor/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-doctor/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-dump-src/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-dump-src/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-load-diff-src/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-load-diff-src/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-load-src/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/1c-load-src/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/1c-load-task-src/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-load-task-src/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-publish-http/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-publish-http/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-run-bdd/SKILL.md` | managed | перенести | Зеркало `.agents/skills/1c-run-bdd/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/1c-run-smoke/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-run-smoke/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/1c-update-db/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/1c-update-db/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/README.md` | managed | обобщить | Добавлены правило «`.agents/skills` — источник, `.claude/skills` — зеркало», `repo-agent-verify` и раздел проектных навыков; генерируется `imported_skills.py`, проектный раздел вынести. | 7.1 |
| `.claude/skills/cf-edit/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cf-edit/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cf-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cf-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cf-init/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cf-init/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cf-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cf-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cfe-borrow/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/cfe-borrow/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/cfe-diff/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cfe-diff/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cfe-init/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cfe-init/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cfe-patch-method/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cfe-patch-method/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/cfe-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/cfe-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/db-create/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-create/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-dump-cf/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-dump-cf/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-dump-xml/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-dump-xml/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-list/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/db-list/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/db-load-cf/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-load-cf/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-load-git/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-load-git/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-load-xml/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-load-xml/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/db-run/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-run/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 1.5 |
| `.claude/skills/db-update/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/db-update/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/epf-add-form/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/epf-add-form/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/epf-bsp-add-command/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/epf-bsp-add-command/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/epf-bsp-init/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/epf-bsp-init/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/epf-build/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/epf-build/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/epf-dump/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/epf-dump/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/epf-init/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/epf-init/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/epf-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/epf-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/erf-build/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/erf-build/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/erf-dump/SKILL.md` | managed | обобщить | Зеркало `.agents/skills/erf-dump/SKILL.md`: решение по источнику; файл строит `make sync-claude-skills`. | 3.3 |
| `.claude/skills/erf-init/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/erf-init/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/erf-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/erf-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/form-add/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-add/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/form-compile/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-compile/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/form-edit/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-edit/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/form-info/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-info/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/form-patterns/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/form-patterns/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/form-remove/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-remove/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/form-validate/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/form-validate/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/help-add/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/help-add/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/img-grid/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/img-grid/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/interface-edit/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/interface-edit/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/interface-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/interface-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/meta-compile/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/meta-compile/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/meta-edit/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/meta-edit/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/meta-info/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/meta-info/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/meta-remove/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/meta-remove/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/meta-validate/SKILL.md` | убран из списка | вывести | Зеркало выводимого `.agents/skills/meta-validate/SKILL.md` (Р6); `make sync-claude-skills` перестаёт его создавать. | 2.7 |
| `.claude/skills/mxl-compile/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/mxl-compile/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/mxl-decompile/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/mxl-decompile/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/mxl-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/mxl-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/mxl-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/mxl-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/role-compile/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/role-compile/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/role-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/role-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/role-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/role-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/skd-compile/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/skd-compile/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/skd-edit/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/skd-edit/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/skd-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/skd-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/skd-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/skd-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/subsystem-compile/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/subsystem-compile/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/subsystem-edit/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/subsystem-edit/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/subsystem-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/subsystem-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/subsystem-validate/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/subsystem-validate/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/template-add/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/template-add/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/template-remove/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/template-remove/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/web-info/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/web-info/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/web-publish/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/web-publish/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/web-stop/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/web-stop/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/web-test/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/web-test/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.claude/skills/web-unpublish/SKILL.md` | managed | уже есть | Проект скопировал в зеркало неизменённый `.agents/skills/web-unpublish/SKILL.md`; HEAD строит зеркало командой `make sync-claude-skills`. | — |
| `.codex/README.md` | managed | обобщить | Описаны примеры `config.{linux,windows}.example.toml`, игнорируемый рабочий `.codex/config.toml`, launcher `bsl-analyzer-workspace` и `one-c-form-viewer`; схема общая, но `one-c-form-viewer` и навык `1c-form-viewer` не входят в состав change. | 3.3 |
| `.contextignore` | managed | оставить в проекте | Добавлено исключение `src/**` из экспорта контекста; это выбор проекта с большой выгрузкой, а в шаблоне `src/` входит в контекст; проектной точки расширения для `.contextignore` нет. | — |
| `.gitattributes` | managed | обобщить | Общие правила `-text`/`-whitespace` для `automation/testing/*` и `src/epf\|erf` смешаны с путями `migration/bp20-*`; переносить только общие строки. | 3.3 |
| `.github/actions/setup-openspec/action.yml` | managed | перенести | Версия OpenSpec закреплена на `1.6.0` вместо `latest`, добавлена проверка `$LASTEXITCODE` после установки; правка не зависит от проекта. | 3.3 |
| `.github/workflows/ci.yml` | managed | обобщить | CI переведён на `astral-sh/setup-uv` + `uv sync --locked`, единый шаг `agent-verify` и pytest переносимых регрессий; требует `pyproject.toml`/`uv.lock` шаблона и тестов `test_cross_platform_*`, которых в шаблоне нет. | 3.2 |
| `.gitignore` | managed | обобщить | Общие правила (`.venv/`, `.build/`, `runtime/`, `*.metadata-state/`, `env/.local/`, примеры `.codex/config.*.example.toml`) смешаны с путями `ТНЛ_АдаптацияБП30`, `bp20_*`, `infra/tnl-site`; переносить только общие строки. | 3.3 |
| `Makefile` | managed | обобщить | Добавлены `python-setup`, `type-check*`, `analyze-bsl-external`, `check-cf-modules`, `technological-log`, удалён `format-bsl`; рядом проектные цели `delivery-*`, `chtz-*`, `month-close`, `bp30-checkpoint-*`, которым нужна project-owned точка расширения Makefile. | 3.2 |
| `automation/context/template-managed-paths.txt` | managed | обобщить | Добавлены пути basedpyright-gate, удалены пути выведенных `meta-*`/`form-*`/`cfe-borrow`, `format-bsl.*` и `tests/golden/run.sh`; список в шаблоне строится заново по итогам 2.7, 3.2 и 7.1. | 7.1 |
| `automation/vendor/cc-1c-skills/imported-skills.json` | managed | обобщить | Удалены записи 12 выведенных навыков, добавлены `argument_hint` профильных диспетчеров и `preferred_native_skills: [1c-run-client]` для `db-run`; выводится генератором вместе с 2.7. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-borrow/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `cfe-borrow` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-borrow/scripts/cfe-borrow.ps1` | убран из списка | вывести | Файл vendor-навыка `cfe-borrow` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-borrow/scripts/cfe-borrow.py` | убран из списка | вывести | Файл vendor-навыка `cfe-borrow` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-init/SKILL.md` | managed | обобщить | Описан новый параметр `-XmlFormat` (`2.17`/`2.20`); правка vendor-файла теряется при `sync-imported-skills`, нужен механизм патчей шаблона. | 3.3 |
| `automation/vendor/cc-1c-skills/skills/cfe-init/scripts/cfe-init.py` | managed | обобщить | Добавлены `-XmlFormat` (по умолчанию формат базы, без базы `2.17`) и запись XML с LF; правка vendor-файла требует механизма патчей шаблона. | 3.3 |
| `automation/vendor/cc-1c-skills/skills/cfe-patch-method/SKILL.md` | managed | обобщить | Ссылка на выводимый `/cfe-borrow` заменена на `metadata-use` (`object.borrow`/`form.borrow`); нужна вместе с выводом `cfe-borrow` и механизмом патчей vendor. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-patch-method/scripts/cfe-patch-method.ps1` | managed | обобщить | Сообщение об ошибке ссылается на `metadata-use` и `form.borrow` вместо выводимого `/cfe-borrow`; правка vendor-файла требует механизма патчей шаблона. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/cfe-patch-method/scripts/cfe-patch-method.py` | managed | обобщить | Сообщение об ошибке ссылается на `metadata-use` и `form.borrow` вместо выводимого `/cfe-borrow`; правка vendor-файла требует механизма патчей шаблона. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/db-create/scripts/db-create.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-dump-cf/scripts/db-dump-cf.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-dump-xml/scripts/db-dump-xml.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-load-cf/scripts/db-load-cf.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-load-git/scripts/db-load-git.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-load-xml/scripts/db-load-xml.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-run/SKILL.md` | managed | обобщить | Описан параметр `-Wait`: ожидание наблюдаемого клиента и возврат кода общего платформенного адаптера. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-run/scripts/db-run.py` | managed | обобщить | Запуск через `onec_xpra.py`, маскирование пароля, параметры `-Out` и `-Wait` (ожидание наблюдаемого клиента). | 1.3 |
| `automation/vendor/cc-1c-skills/skills/db-update/scripts/db-update.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/epf-build/SKILL.md` | managed | обобщить | Автопоиск платформы на Linux (`/opt/1cv8/x86_64/*/1cv8`) и запуск Designer через `direct-platform` под Xpra. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/epf-build/scripts/epf-build.py` | managed | обобщить | Запуск Designer и временной ИБ через `onec_xpra.py`, маскирование пароля, вывод stdout/stderr; правка vendor-файла требует механизма патчей шаблона. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/epf-build/scripts/stub-db-create.py` | managed | обобщить | Запуск Designer и временной ИБ через `onec_xpra.py`, маскирование пароля, вывод stdout/stderr; правка vendor-файла требует механизма патчей шаблона. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/epf-dump/SKILL.md` | managed | обобщить | Автопоиск платформы на Linux и уточнение `-V8Path`; следует за переносом запуска через `onec_xpra`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/epf-dump/scripts/epf-dump.py` | managed | обобщить | Запуск 1cv8 через проектный `scripts/python/onec_xpra.py` (Linux, Xpra), маскирование пароля, `/S` одним аргументом; diff однотипен для 8 db-*/epf-dump скриптов, оценено по образцу `db-create.py`. | 1.3 |
| `automation/vendor/cc-1c-skills/skills/erf-init/SKILL.md` | managed | обобщить | Ссылка на выводимый `/form-add` заменена на `metadata-use` и `form.create` (строки с CRLF); нужна вместе с выводом `form-*`. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-add/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-add` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-add/scripts/form-add.ps1` | убран из списка | вывести | Файл vendor-навыка `form-add` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-add/scripts/form-add.py` | убран из списка | вывести | Файл vendor-навыка `form-add` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-compile/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-compile/scripts/form-compile.ps1` | убран из списка | вывести | Файл vendor-навыка `form-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-compile/scripts/form-compile.py` | убран из списка | вывести | Файл vendor-навыка `form-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-edit/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-edit/scripts/form-edit.ps1` | убран из списка | вывести | Файл vendor-навыка `form-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-edit/scripts/form-edit.py` | убран из списка | вывести | Файл vendor-навыка `form-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-info/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-info/scripts/form-info.ps1` | убран из списка | вывести | Файл vendor-навыка `form-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-info/scripts/form-info.py` | убран из списка | вывести | Файл vendor-навыка `form-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-patterns/SKILL.md` | managed | обобщить | Ссылка на выводимый `/form-compile` заменена на `metadata-use` и `form.compile`; `form-patterns` остаётся по Р6. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-remove/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-remove/scripts/remove-form.ps1` | убран из списка | вывести | Файл vendor-навыка `form-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-remove/scripts/remove-form.py` | убран из списка | вывести | Файл vendor-навыка `form-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-validate/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `form-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-validate/scripts/form-validate.ps1` | убран из списка | вывести | Файл vendor-навыка `form-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/form-validate/scripts/form-validate.py` | убран из списка | вывести | Файл vendor-навыка `form-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/reference/types-basic.md` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/reference/types-process.md` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/reference/types-registers.md` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/reference/types-web.md` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/scripts/meta-compile.ps1` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-compile/scripts/meta-compile.py` | убран из списка | вывести | Файл vendor-навыка `meta-compile` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/child-operations.md` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/json-dsl.md` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/properties-reference.md` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/scripts/meta-edit.ps1` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-edit/scripts/meta-edit.py` | убран из списка | вывести | Файл vendor-навыка `meta-edit` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-info/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `meta-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-info/scripts/meta-info.ps1` | убран из списка | вывести | Файл vendor-навыка `meta-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-info/scripts/meta-info.py` | убран из списка | вывести | Файл vendor-навыка `meta-info` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-remove/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `meta-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-remove/scripts/meta-remove.ps1` | убран из списка | вывести | Файл vendor-навыка `meta-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-remove/scripts/meta-remove.py` | убран из списка | вывести | Файл vendor-навыка `meta-remove` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-validate/SKILL.md` | убран из списка | вывести | Файл vendor-навыка `meta-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-validate/scripts/meta-validate.ps1` | убран из списка | вывести | Файл vendor-навыка `meta-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `automation/vendor/cc-1c-skills/skills/meta-validate/scripts/meta-validate.py` | убран из списка | вывести | Файл vendor-навыка `meta-validate` выводится по Р6; проект удалил его из списка и дерева. | 2.7 |
| `docs/agent/codex-workflows.md` | managed | обобщить | Добавлен раздел CLI `metadata` (`capabilities/inspect/plan/apply/verify`) и раздел «Разработка на двух ОС»; ссылки на архивные changes проекта (`2026-09-10-add-managed-form-cli` и др.) нужно убрать. | 2.3 |
| `docs/agent/generated-project-verification.md` | managed | обобщить | Требования Python 3.12+/OpenSpec 1.6.0, цель `type-check` и раздел парной проверки кандидата на Linux и Windows; раздел ссылается на тесты `test_cross_platform_*` и MCP-smoke, которых в шаблоне нет. | 3.2 |
| `docs/agent/verify.md` | managed | перенести | Добавлены команды `type-check-setup`, `type-check`, `type-check-update-baseline` и правило сокращения базовой линии; текст не содержит проектных имён. | 3.2 |
| `env/README.md` | managed | обобщить | Общие правила (корневой `.env` с правами `0600`, независимые Linux/Windows checkout) смешаны с профилями `bp20-delivery-build`, `bp20-anonymization-work` и базой `tn_bp20_custom_mcp`; переносить только общие абзацы. | 3.3 |
| `make.ps1` | managed | обобщить | Добавлены `python-setup`, `type-check*`, `sync-claude-skills`, удалён `format-bsl`; ветка `delivery-*` проектная; HEAD шаблона уже содержит `sync-claude-skills` и Windows-цели CFE, поэтому правку накладывать на HEAD. | 3.2 |
| `scripts/adapters/direct-platform.sh` | managed | обобщить | Встроены наблюдение запуска (`start/finish_native_observation`, техжурнал), очистка зависших Xvfb/Xpra, выбор номера дисплея под блокировкой, `modal_policy`, сброс `TZ`; переносится в адаптер наблюдения шаблона. | 1.3 |
| `scripts/bootstrap/agents-overlay.sh` | managed | уже есть | HEAD уже содержит формулировку push «только по запросу» и приоритет проектного поискового регламента; осталось только удаление блока `rlm-tools`, оно вынесено на решение координатора. | — |
| `scripts/diag/doctor.sh` | managed | обобщить | Добавлены `reject_unsupported_override_flag` и вызов `target_require_requested` в подоболочке; в HEAD `doctor` переведён на Python, правку нужно перенести в Python-runtime. | 3.3 |
| `scripts/lib/capability.sh` | managed | обобщить | Добавлен общий адаптер наблюдения `run_observed_command` (`observation.jsonl`, heartbeat, терминальное событие, техжурнал, Windows-путь через `observe-command`); это источник задачи 1.1, в HEAD основные платформенные команды идут через Python. | 1.1 |
| `scripts/lib/common.sh` | managed | обобщить | Добавлены автозагрузка корневого `.env` без перезаписи заданных переменных и вынос артефактов за пределы checkout; путь `.tn-bp30-sdd-artifacts` и вызов проектного `scripts/artifact_storage.py` нужно обобщить. | 3.3 |
| `scripts/lib/designer-diagnostics.sh` | managed | обобщить | Добавлены англ./рус. строки «Синтаксических ошибок не обнаружено» и удалена текстовая проверка наличия процедуры в BSL (`designer_bsl_symbol_exists`) по D5; в HEAD логика нужна в Python-runtime. | 2.1 |
| `scripts/lib/ibcmd.sh` | managed | обобщить | Добавлены `ibcmd.auth.mode=none`, `ibcmd.locale`, `dumpSrc.sourceFile`, `--info-only` и `--sync` для выгрузки; в HEAD этих режимов нет, переносить в Python-runtime `dump-src`. | 3.3 |
| `scripts/lib/onec.sh` | managed | обобщить | Добавлены разовый `--override-unsupported-profile` для частичной загрузки в расходуемые базы, `--source-dir`/`--output-dir`, `--info-only`, `--vendor-cf` (Designer `/UpdateCfg`) и отложенное терминальное событие; переносить в Python-runtime HEAD. | 3.3 |
| `scripts/lib/runtime-profile.sh` | managed | обобщить | Добавлены удаление CR из вывода `jq` на Windows и функция `runtime_profile_unsupported_override_allowed` (список расходуемых профилей в policy); в HEAD нужен Python-эквивалент. | 3.3 |
| `scripts/lib/target-matrix.sh` | managed | обобщить | Добавлены удаление CR из значений и параметр `require_directory`; CR-проблема относится к Git Bash на Windows, которого HEAD больше не требует, параметр нужен Python-runtime. | 3.3 |
| `scripts/llm/export-context.sh` | managed | перенести | Shell-реализация (780 строк) заменена делегированием в `run-python.sh export-context`; Python-реализация уже есть в HEAD и вызывается из `export-context.ps1`. | 3.3 |
| `scripts/platform/check-cfe-applicability.sh` | managed | обобщить | Запуск обёрнут в `run_observed_command` с техжурналом `rphost`, `observation` добавлено в `summary.json`; в HEAD сценарий — тонкий вызов Python, наблюдение подключать там. | 1.3 |
| `scripts/platform/check-cfe-config.sh` | managed | обобщить | Добавлены `--source-root`, `--syntax-only` и запуск через `run_observed_command`; в HEAD сценарий — тонкий вызов Python, правки переносить в `cfe_runtime.py`. | 1.3 |
| `scripts/platform/configure-cfe-runtime-flags.sh` | managed | обобщить | Добавлены `--target`, `--active`, `--security-profile-name`/`--clear-security-profile`, отбор только реальных каталогов расширений и сопоставление имён без учёта регистра по `extension list`; переносить в Python-runtime HEAD. | 3.3 |
| `scripts/platform/create-ib.sh` | managed | обобщить | Добавлена регистрация клиент-серверной ИБ в кластере через `rac` после `ibcmd` (`register_ibcmd_client_server_infobase`); в HEAD сценарий — тонкий вызов Python. | 3.3 |
| `scripts/platform/dump-src.sh` | managed | обобщить | Добавлены `--output-dir` и `--info-only` (только `ConfigDumpInfo.xml` через ibcmd); в HEAD сценарий — тонкий вызов Python. | 3.3 |
| `scripts/platform/load-cfe.sh` | managed | обобщить | Добавлены `--source-root`, наблюдаемый запуск и повтор после `repair` при незавершённом применении поколения; в HEAD сценарий — тонкий вызов Python. | 1.3 |
| `scripts/platform/load-diff-src.sh` | managed | обобщить | Добавлен только `reject_unsupported_override_flag`; в HEAD сценарий — тонкий вызов Python, проверку перенести туда. | 3.3 |
| `scripts/platform/load-src.sh` | managed | обобщить | Добавлены `--source-dir` и `--override-unsupported-profile` (только с `--files` и `--run-root`, запись в `summary.json`); в HEAD сценарий — тонкий вызов Python. | 3.3 |
| `scripts/platform/manage-cfe.sh` | managed | обобщить | Добавлены действия без расширения, `--driver designer`/`--via-designer`, `--list-file`, `--output`, `--file`, наблюдаемый запуск Designer; комментарий про базу правил КД проектный; в HEAD сценарий — тонкий вызов Python. | 1.3 |
| `scripts/platform/publish-http.sh` | managed | обобщить | В справку добавлен `--target`; в HEAD сценарий — тонкий вызов Python, проверить наличие `--target` там. | 3.3 |
| `scripts/platform/update-db.sh` | managed | обобщить | Добавлен `--vendor-cf` (Designer `/UpdateCfg` из CF поставщика перед `/UpdateDBCfg`); в HEAD сценарий — тонкий вызов Python. | 3.3 |
| `scripts/platform/v8unpack.sh` | managed | обобщить | Добавлены действия `container-extract\|container-build` через `v8unpack_container.py` и отдельный `TMPDIR` в run-root; цель `v8unpack` в HEAD убрана из Makefile, нужно согласовать. | 2.4 |
| `scripts/python/cli.py` | managed | обобщить | Добавлены команды `metadata`, `observe-command`, `manage-cfe`, `run-client`, `cluster-*`, `type-check*`, `sync-claude-skills`, `ordinary-form-conversion`, удалён `format-bsl`; `sync-claude-skills` уже есть в HEAD, остальное раскладывается по задачам. | 3.3 |
| `scripts/python/common.py` | managed | обобщить | `die` типизирован как `NoReturn`, добавлены `resolve_openspec_path`, `object_dict`, `object_list` для basedpyright-gate; накладывать на HEAD. | 3.2 |
| `scripts/python/context.py` | managed | обобщить | Экспорт контекста: снимок инвентаря, скрытие каталогов вроде `.build`, метаданные целей из `target-matrix`, счётчики `src/*`; накладывать на изменённый HEAD. | 3.3 |
| `scripts/python/epf_templates.py` | managed | перенести | Подсказка следующего шага заменена с `form-validate` на `metadata verify`; переносится вместе с выводом `form-*`. | 2.7 |
| `scripts/python/imported_skills.py` | managed | обобщить | Добавлены `RETIRED_METADATA_SKILLS`, профильные диспетчеры ibcmd без перехода на Designer, прокси `db-run` → `run-client`, сборка EPF/ERF через `file-import`; HEAD переписал модуль и уже содержит зеркало `sync_claude_skills`. | 2.7 |
| `scripts/python/qa.py` | managed | обобщить | Добавлены `analyze-bsl` через MCP `bsl-analyzer`, проверка путей в `SKILL.md`, Goal Cursor, расширенный `agent_verify`, удалён `format_bsl`; проектные шаги (`BP20 comparison secrets`, `ChTZ register`, `ТНЛ_АдаптацияБП30`) вынести в project-specific baseline extension. | 3.1 |
| `scripts/python/run-python.ps1` | managed | обобщить | Обработка `--`, UTF-8 консоль, выбор `.venv`/`uv run --locked`, команда `python-setup`; требует `pyproject.toml`/`uv.lock` шаблона. | 3.2 |
| `scripts/python/run-python.sh` | managed | обобщить | Режим `-- <python-args>`, загрузка `common.sh`, выбор `.venv`/`uv run --locked`, `python-setup` через `uv sync`; требует `pyproject.toml`/`uv.lock` шаблона. | 3.2 |
| `scripts/python/runtime.py` | managed | обобщить | Добавлены Windows `observe-command` (лимиты `observation.jsonl`) и Windows `manage-cfe`; по D4 Windows-наблюдение переносится в отдельный модуль `runtime_observation.py`, а не копированием `runtime.py`. | 1.1 |
| `scripts/qa/agent-verify.sh` | managed | перенести | Shell-реализация заменена делегированием в `run-python.sh agent-verify`; Python-реализация есть в HEAD, состав шагов переносится в `qa.py`. | 3.3 |
| `scripts/qa/analyze-bsl.sh` | managed | перенести | Shell-запуск BSL LS заменён делегированием в `run-python.sh analyze-bsl`; новая логика находится в `qa.py`. | 2.1 |
| `scripts/qa/check-agent-docs.sh` | managed | перенести | Shell-реализация (1227 строк) заменена делегированием в `run-python.sh check-agent-docs`; Python-реализация уже есть в HEAD. | 3.3 |
| `scripts/qa/format-bsl.ps1` | убран из списка | оставить в проекте | Windows-обёртка `format-bsl`; проект удалил её вместе с `format-bsl.sh`. | — |
| `scripts/qa/format-bsl.sh` | убран из списка | оставить в проекте | Проект удалил форматирование BSL LS (`format-bsl`) и убрал путь из своего списка; в HEAD цель остаётся, удаление из шаблона вынесено на решение координатора. | — |
| `scripts/test/run-bdd-warm-run.sh` | managed | перенести | Добавлена запись прогресса фич в `observation-progress` для heartbeat адаптера наблюдения. | 1.3 |
| `scripts/test/run-bdd-warm-service.sh` | managed | перенести | Команды `up\|down` открывают `observation.jsonl` и закрывают его в `EXIT` trap, heartbeat в циклах ожидания. | 1.3 |
| `scripts/test/run-golden-baseline.sh` | managed | обобщить | Запуск через `run_observed_command`, `observation` в `summary.json`, нормализация путей; строка справки про BP30 restore и `GOLDEN_BASELINE_RUN_ID` проектная. | 1.3 |
| `scripts/test/run-yaxunit-warm-service.sh` | managed | обобщить | Добавлены наблюдение, блокировка профиля, скрытие кода доступа сеанса, построчный вывод упавших тестов; путь блокировки `tn-bp30-sdd-kd21-locks` общий с исполнителем КД проекта и требует обобщения. | 1.3 |
| `scripts/test/run-yaxunit.sh` | managed | обобщить | Наблюдение запуска, автоматический выбор расширений по `filter.tests` вида `module.method`, подсказка команды синхронизации; накладывать на HEAD. | 1.3 |
| `tests/golden/README.md` | managed | оставить в проекте | Текст переписан под проектное восстановление `bp30_exchange_work` и `bp20_anonymization_work`; общий README шаблона должен ссылаться на project-owned `tests/golden/run.sh`, а проектный текст — жить в проектной документации. | — |
| `tests/golden/db.sh` | managed | обобщить | Добавлены `--create-only`, `--verbose`/`--exit-on-error` для `pg_restore`; вызовы проектного `artifact_storage` (паспорт хранения) нужно убрать или обобщить. | 3.3 |
| `tests/golden/run.sh` | убран из списка | оставить в проекте | Проект заменил `run.sh` своим восстановлением `bp30_exchange_work` и вывел путь из списка; шаблонный README сам предлагает заменить `run.sh`, project-owned точка — сам файл. | — |
| `tests/python/test_cross_platform.py` | managed | обобщить | Добавлены проверки импорта `cli` без `v8unpack`, кешей `__pycache__` и генерации навыков; накладывать на HEAD вместе с 2.4 и 2.7. | 3.3 |
| `tests/python/test_epf_init_from_template_command.py` | managed | обобщить | Из сравнения текста исключены файлы `.bsl` и сняты проверки содержимого BSL (запрет текстовых проверок BSL по D5). | 3.3 |
| `tests/python/test_epf_templates_form_title_version.py` | managed | обобщить | Проект удалил тест, который проверял регулярным выражением текст BSL шаблонов EPF; по D5 текстовые проверки BSL не допускаются, удаление вынесено на решение координатора. | 3.3 |
| `tests/smoke/agent-docs-contract.sh` | managed | обобщить | Проверки исключения `.build` из `source-tree.generated.txt`, подсказки `make export-context-write` и наличия её в навыке архивации; формулировка push уже есть в HEAD. | 3.3 |
| `tests/smoke/bootstrap-agents-overlay.sh` | managed | уже есть | Файл проекта совпадает с HEAD шаблона (новая формулировка push). | — |
| `tests/smoke/check-cfe-applicability-contract.sh` | managed | обобщить | Добавлены проверки `observation.jsonl` и одного терминального события; следует за переносом наблюдения в Python-runtime. | 1.4 |
| `tests/smoke/check-cfe-config-contract.sh` | managed | обобщить | Проверки наблюдения, `--syntax-only` и разбора диагностик общих модулей; следует за переносом `check-cfe-config` в Python-runtime. | 1.4 |
| `tests/smoke/configure-cfe-runtime-flags-contract.sh` | managed | обобщить | Проверки отбора каталогов расширений и флагов `--safe-mode`/`--security-profile-name`; имя `tnl-bp30-bootstrap` заменить фикстурным. | 3.3 |
| `tests/smoke/copier-update-ready.sh` | managed | обобщить | Формулировка push уже есть в HEAD; добавить проверку, что `.artifacts` не попадает в `source-tree.generated.txt`. | 3.3 |
| `tests/smoke/golden-baseline-contract.sh` | managed | обобщить | Переменные `ONEC_ARTIFACT_ROOT`/`ONEC_RUN_RESERVE_BYTES` проектного хранилища и журнал вызовов `pg_*`; следует за решением по `tests/golden/db.sh`. | 3.3 |
| `tests/smoke/imported-skills-contract.sh` | managed | обобщить | Проверки профильной сборки `epf/erf-build`, `--help` и выведенных навыков в `imported_skills`; накладывать на переписанный в HEAD модуль. | 2.7 |
| `tests/smoke/load-cfe-contract.sh` | managed | обобщить | Проверки автозагрузки `.env`, `--source-root` и повтора после `repair`; следует за переносом `load-cfe` в Python-runtime. | 3.3 |
| `tests/smoke/manage-cfe-contract.sh` | managed | обобщить | Проверки `dump`/`save`, Designer-драйвера и `--list-file`; следует за переносом `manage-cfe` в Python-runtime. | 3.3 |
| `tests/smoke/reusable_testing_contract.py` | managed | перенести | Порядок обхода файлов для хеша дерева сделан по компонентам POSIX (стабилен на Windows) и добавлен закреплённый хеш-тест. | 3.3 |
| `tests/smoke/runtime-capability-contract.sh` | managed | обобщить | Фикстура получает `ONEC_ARTIFACT_ROOT` и цель из `target-matrix.json`; часть про хранилище артефактов зависит от решения по `common.sh`. | 3.3 |
| `tests/smoke/runtime-direct-platform-xpra-contract.sh` | managed | обобщить | Проверки наблюдения и техжурнала в `direct-platform`, очистки процессов Xpra; путь `src/cf/tn_bp30_sdd` заменить фикстурным. | 1.4 |
| `tests/smoke/runtime-doctor-contract.sh` | managed | обобщить | Добавлена текстовая проверка удаления CR в `runtime-profile.sh`; в HEAD доктор на Python, проверку переписать на поведение. | 3.3 |
| `tests/smoke/runtime-ibcmd-capability-contract.sh` | managed | обобщить | Проверки деградированного наблюдения, Designer-драйверов и policy `unsupportedOverride`; цель `tn_bp30_sdd` и профиль `env/bp30-exchange-work.json` заменить фикстурными. | 3.3 |
| `tests/smoke/v8unpack-contract.sh` | managed | обобщить | Проверки `TMPDIR` в run-root и действий `container-extract\|container-build`; требует `v8unpack_container.py` из 2.4. | 2.4 |
| `tests/smoke/vanessa-bdd-warm-service-contract.sh` | managed | перенести | Проверки `observation.jsonl` для `up` и прогресса фич в warm-run; без проектных имён. | 1.4 |
| `tests/smoke/yaxunit-contour-contract.sh` | managed | обобщить | Фикстуры тайм-аута, падения и выбора расширения по модулю теста; следует за правкой `run-yaxunit.sh`. | 1.4 |
| `tests/smoke/yaxunit-warm-rpc-contour-contract.sh` | managed | обобщить | Проверки блокировки профиля, остановки процессов контроллера и клиента; следует за обобщением `run-yaxunit-warm-service.sh`. | 1.4 |

## Требует решения координатора

1. **Патчи vendor-файлов `cc-1c-skills`.** Проект правил 21 vendor-файл в `automation/vendor/cc-1c-skills/skills/` (запуск через `onec_xpra.py`, `-XmlFormat`, `-Wait`, ссылки на `metadata-use`). `sync-imported-skills` перезаписывает vendor-дерево из upstream, поэтому прямые правки потеряются. Нужно выбрать один из вариантов:
   - хранить правки как патчи шаблона, которые применяются после синхронизации;
   - перенести поведение в repo-owned диспетчер `imported_skills.py`.

   Отдельно решить, какой модуль заменяет проектный `scripts/python/onec_xpra.py`. Этот файл не входит в 251 путь, а vendor-скрипты проекта его импортируют. Вероятно, это общий адаптер наблюдения из задачи 1.1.
2. **Профильные диспетчеры ibcmd без перехода на Designer.** `imported_skills.py` проекта переводит `db-*` и `epf/erf-build|dump` на обязательные `--profile/--target` через ibcmd, убирает автоматическую временную ИБ и переход на Designer. Это меняет видимое поведение импортированных навыков для всех проектов, а в задачах change такого пункта нет. Нужно решить: включать изменение в базовый набор (тогда нужна запись в release notes) или оставить прежнее поведение.
3. **Удаление `format-bsl`.** Проект удалил `scripts/qa/format-bsl.{sh,ps1}`, цель `format-bsl` и функцию `format_bsl`. В инвентаре стоит `оставить в проекте`, то есть шаблон сохраняет `format-bsl`. Если шаблон должен тоже убрать форматирование, решение нужно поменять на `перенести` и добавить запись в release notes.
4. **Блок `rlm-tools` в `scripts/bootstrap/agents-overlay.sh`.** Остальные правки уже есть в HEAD, но проект ещё удалил рекомендацию `rlm-tools`. Нужно решить, удалять ли её из шаблона.
5. **Текстовые проверки BSL в тестах EPF.** Проект удалил `tests/python/test_epf_templates_form_title_version.py` и снял проверки BSL-текста в `test_epf_init_from_template_command.py`. D5 запрещает разбирать синтаксис BSL тестами, но эти тесты проверяют наличие фрагментов в шаблонах обработок. Нужно решить, удалять ли их в шаблоне.
6. **Точки расширения для проектных фрагментов в template-managed файлах.** В HEAD нет project-owned точек расширения для:
   - проектных целей `Makefile`/`make.ps1`: `delivery-*`, `chtz-*`, `month-close`, `bp30-checkpoint-*`;
   - проектных шагов `agent_verify`: `BP20 comparison secrets`, `ChTZ register`. Возможный путь — `projectSpecificBaselineExtension` из `runtime-support-matrix.json`;
   - проектных строк `.gitignore`, `.gitattributes`, `.contextignore`;
   - проектных разделов `.agents/skills/README.md`, `.claude/skills/README.md`, `env/README.md`, `tests/golden/README.md`.

   Нужно решить, какие точки добавить: например, `-include` проектного Makefile или project-owned раздел README. Иначе эти фрагменты потеряются при `template-update` проекта.
7. **`tests/golden/run.sh` как project-owned путь.** README шаблона предлагает заменить `run.sh` проектным сценарием, но путь остаётся template-managed. Нужно решить, переводить ли `tests/golden/run.sh` (и, возможно, `tests/golden/README.md`) в preserve-контракт шаблона (задача 7.1).
8. **Хранилище артефактов вне checkout и `artifact_storage.py`.** `scripts/lib/common.sh` проекта по умолчанию выносит артефакты в `../.tn-bp30-sdd-artifacts`, а `tests/golden/db.sh` пишет паспорт хранения через `scripts/artifact_storage.py`. Этого механизма нет в proposal. Нужно решить, включать ли его в базовый набор с нейтральным именем каталога или оставить автозагрузку `.env` без него.
9. **Изменения без отдельной задачи в `tasks.md`.** Следующие изменения отнесены к задаче 3.3, но по объёму это отдельные функции; нужно подтвердить, что они входят в базовый набор:
   - `--override-unsupported-profile` и `unsupportedOverride` в policy;
   - `--vendor-cf` для `update-db`;
   - `--info-only` и `dumpSrc.sourceFile` для `dump-src`;
   - регистрация ИБ в кластере через `rac` после `create-ib`;
   - флаги безопасности в `configure-cfe-runtime-flags`;
   - Designer-драйвер `manage-cfe`;
   - парная проверка кандидата на Linux и Windows в `generated-project-verification.md`;
   - `one-c-form-viewer` в `.codex/README.md`.
10. **Цель `v8unpack`.** В HEAD цель `v8unpack` удалена из `Makefile`, хотя сценарий `scripts/platform/v8unpack.sh` остался. Проект расширяет этот сценарий действиями `container-*` (задача 2.4). Нужно подтвердить, через какую точку входа шаблон поставляет `v8unpack`.
11. **Повторная сверка.** Перед задачей 3.3 нужно повторить сверку по D7 для файлов проекта, изменённых после коммита `099860613`.
