# Project Rules

## Цель шаблона

Этот репозиторий предназначен для 1С-проектов, где разработка идет по схеме:

- `OpenSpec -> Beads -> Code`
- явная цепочка `Requirement -> Code -> Test`
- `runner-agnostic execution`
- `LLM-friendly repository layout`

## Единый Workflow

### 1. Intent Formation

- Любая новая capability, breaking change, архитектурный сдвиг, заметная performance/security работа или неоднозначная задача начинается с change в `openspec/changes/<change-id>/`.
- До начала кодовых правок change должен быть доведен до подписываемого контракта как минимум через `proposal.md`, один или несколько `specs/<capability>/spec.md`, `tasks.md` и `traceability.md`.
- Для новых и крупных изменений в код нельзя переходить без явного согласования. Канонический сигнал: `Go!`.
- До согласования допустимы анализ, уточнение требований и правки spec-артефактов, но не production code.

### 2. Task Transformation

- После согласования change должен быть переведен в исполняемый план в `bd`, а не оставаться только markdown-текстом.
- Для code-change источником истины по задачам является `bd`: перед началом работы запускать `bd prime`, затем работать от `bd ready`.
- Не использовать markdown TODO/checklist как параллельный трекер кодовых задач.
- Если beads был явно отключен при создании проекта, это нужно проговорить как исключение и не подменять `bd` молчаливым ad-hoc трекингом.

### 3. Исполнение И Доставка

- Перед кодингом строить execution matrix: `Requirement/Scenario -> target files -> automated checks`.
- Каждый обязательный `MUST`/Requirement/Scenario должен иметь automated evidence в `tests/` или `features/`, либо явно одобренное пользователем исключение.
- Статусы `partially implemented` или `not implemented` для обязательных требований блокируют завершение change.
- Финальный отчет по change обязан содержать явную трассировку `Requirement -> Code -> Test` с конкретными путями файлов.

## Источники истины

1. `openspec/changes/<change-id>/specs/<capability>/spec.md` — требования и capability deltas
2. `.beads/` — live task graph и статус исполнения, если beads включен
3. `tests/` и `features/` — автоматизированные проверки
4. `src/` — production source tree
5. `openspec/changes/<change-id>/traceability.md` — матрица доставки

## Базовые правила

- Отвечай и пиши документацию на русском языке по умолчанию.
- Не складывай новые задачи в `src/task_*`.
- Не смешивай историю изменений и deployable source tree.
- Любое behavior change сначала отражай в `openspec/`.
- Для новых и крупных изменений не переходи к коду до явного `Go!`.
- Если в проекте включен beads, используй `bd` как единственный task tracker для code-change.
- Не веди параллельные markdown TODO-списки для кодовой работы.
- Для обязательных требований сначала добавляй или обновляй тест/acceptance-check.
- Используй канонические входные точки из `scripts/`, а не случайные ad-hoc команды.
- Skills и agent wrappers не должны дублировать runtime logic, уже существующую в `scripts/`.
- Capability-скрипты должны возвращать machine-readable artifacts (`summary.json`, `stdout.log`, `stderr.log`).
- Runtime profiles брать из `env/*.json` через `--profile` или `ONEC_PROFILE`, а не из несвязанных ad-hoc env dumps.
- Не делай `vrunner` обязательной зависимостью, если задача решается через `direct-platform` или `remote-windows`.
- Если в проекте инициализирован beads, перед планированием и исполнением запускай `bd prime`.

## Каталоги

- `src/` — только исходники конфигурации/расширений/EPF/ERF
- `openspec/` — пространство спецификаций и change-артефактов, создаваемое `openspec init`
- `tests/` — code-level тесты и smoke
- `features/` — acceptance/BDD
- `automation/` — контекст для агентов
- `.claude/skills/` — project-scoped agent skills, которые должны ссылаться на repo-owned scripts
- `env/` — canonical runtime profile examples для launcher-скриптов

## Минимальный контракт change

Каждый осмысленный change должен иметь:

- `proposal.md`
- один или несколько `specs/<capability>/spec.md`
- `tasks.md`
- `traceability.md`

Опционально:

- `design.md`

## Поиск По Кодовой Базе

Порядок поиска:

1. semantic search (`mcp__claude-context__search_code`), если он доступен в текущем контуре
2. `ast-index search "<query>"`, если репозиторий его использует или semantic search шумит
3. `rg`
4. `rg --files`
5. точечное чтение файлов

Дополнительный sidecar:

- `rlm-tools` можно использовать для low-context exploration, когда широкий `grep` или массовое чтение файлов создают слишком много сырого вывода.
- `rlm-tools` не является источником истины: итоговые утверждения нужно подтверждать прямыми ссылками на код.

Чек-лист:

1. Формулируй запрос как `component + action + context`.
2. Первый проход делай узким: limit `6-10` результатов или эквивалентное сужение.
3. Сразу ограничивай поиск по расширениям или релевантным каталогам.
4. Если выдача шумная, переформулируй запрос через конкретные сущности.
5. Подтверждай факты минимум в двух источниках: код + тест/spec/README.
6. Не считай TODO/checklist/status-файлы доказательством реализации без проверки исходников.

Индексация:

- Для ручного reindex использовать один канонический absolute path с trailing `/`.
- Для принудительного переиндексирования использовать `force=true`.
- Если semantic tooling недоступен, сразу переходить к `rg`/`rg --files`.

## Verification

После изменений запускать минимально релевантные проверки:

- `./scripts/qa/analyze-bsl.sh`
- `./scripts/qa/check-skill-bindings.sh`
- `./scripts/test/run-xunit.sh`
- `./scripts/test/run-bdd.sh`
- `./scripts/test/run-smoke.sh`

Если конкретный runner в текущем контуре не настроен, нужно явно сообщить, что именно не настроено.

## Завершение Сессии

- Сессия с кодовыми изменениями не считается завершенной, пока `git push` не прошел успешно.
- Перед handoff нужно обновить статус задач, прогнать релевантные quality gates, при необходимости сделать `git pull --rebase`, затем `git push`.
- Если `git push` заблокирован внешним ограничением или явным запретом пользователя, нужно явно назвать блокер в handoff.
