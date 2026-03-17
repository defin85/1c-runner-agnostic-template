# {{ project_name }}

Шаблон проекта для разработки на 1С по принципам:

- `SDD` (`Spec-Driven Development`) через `OpenSpec`
- `TDD` через `tests/` и `features/`
- `beads` для локального issue-tracking в stealth-режиме
- `LLM-first automation` через `PROJECT_RULES.md`, `automation/` и стабильные launcher-скрипты
- `runner-agnostic execution`, где `vrunner` является опциональным адаптером, а не фундаментом проекта

## Ключевая идея

Исходники решения живут в `src/` и только там.

Все, что относится к намерению изменения, после bootstrap лежит в `openspec/changes/<change-id>/`.
Все, что относится к проверке поведения, лежит в `tests/` и `features/`.
Все, что относится к запуску, лежит в `scripts/`.
Локальный трекинг задач, если включен при создании проекта, живет в `.beads/` и не коммитится благодаря stealth-режиму.

Это позволяет:

- не смешивать код с архивом задач;
- менять механизм запуска без перестройки репозитория;
- держать явные цепочки `OpenSpec -> Beads -> Code` и `Requirement -> Code -> Test -> Traceability`.

## Структура

```text
.
├── PROJECT_RULES.md
├── Makefile
├── automation/
├── docs/
├── env/
├── features/
├── scripts/
├── openspec/
├── src/
└── tests/
```

### Что где лежит

- `src/` — deployable source tree: конфигурация, расширения, обработки, отчеты.
- `openspec/` — пространство спецификаций, создаваемое `openspec init`.
- `tests/xunit/` — code-level TDD и unit-style проверки.
- `tests/smoke/` — короткие регрессионные и инфраструктурные проверки.
- `features/` — acceptance / BDD сценарии.
- `scripts/` — канонические входные точки для людей, CI и агентов.
- `env/` — примеры конфигурации окружений.
- `automation/` — контекст и правила для LLM/агентов.
- `docs/` — ADR, архитектурные заметки, эксплуатационная документация.
- `.beads/` — локальная issue-база beads, создается bootstrap-скриптом и скрывается из Git.

## Принцип запуска

В проекте нет жесткой привязки к одному runner.

Все запускатели идут через стабильные entrypoint-скрипты:

- `./scripts/platform/create-ib.sh`
- `./scripts/platform/load-src.sh`
- `./scripts/platform/update-db.sh`
- `./scripts/platform/publish-http.sh`
- `./scripts/test/run-xunit.sh`
- `./scripts/test/run-bdd.sh`
- `./scripts/test/run-smoke.sh`
- `./scripts/qa/analyze-bsl.sh`
- `./scripts/qa/format-bsl.sh`

Backend выбирается через `RUNNER_ADAPTER`:

- `direct-platform`
- `remote-windows`
- `vrunner`

Сами команды задаются через env vars. Примеры есть в `env/*.example.json`.

## Рекомендуемый workflow

1. Создать change в `openspec/changes/<change-id>/`.
2. Зафиксировать требования в `spec.md`.
3. Для новых и крупных изменений получить явное согласование (`Go!`) до перехода к production code.
4. Перевести change в исполняемый план через `bd` и работать от `bd ready`. Если beads отключен, проговорить это как исключение, а не заменять его markdown TODO-списком.
5. Разложить контракт изменения: входы, выходы, инварианты, ограничения.
6. Построить явную матрицу `Requirement -> Code -> Test`.
7. Написать red-check в `tests/` или `features/`.
8. Реализовать код в `src/`.
9. Обновить `traceability.md`.
10. Прогнать узкие проверки через `scripts/test/*` и `scripts/qa/*`.
11. Завершать сессию только после `git push`, если нет внешнего блокера.

## Быстрый старт

1. Создайте новый проект через Copier:

```bash
copier copy <path-or-git-url-to-template> .
```

Или используйте локальную обертку `new-1c-project`, если она установлена:

```bash
new-1c-project ~/code/my-project --defaults
cd ~/code/my-project && new-1c-project --defaults
new-1c-project ~/code/my-project --defaults --no-beads
new-1c-project ~/code/my-project --defaults --beads-prefix docflow
```

`new-1c-project` это не часть сгенерированного проекта, а локальный helper-скрипт поверх `copier copy`.
Если `destination` не указан или равен `.`, helper берёт `project_name` и `project_slug` из имени текущей папки.
Post-copy bootstrap создаёт базовый `AGENTS.md` через `openspec init` и дополняет его типовым project overlay с workflow, rules для `bd` и playbook поиска по коду.
Шаблон также сохраняет `.copier-answers.yml`, чтобы сгенерированный проект можно было обновлять через `copier update`.

2. Убедитесь, что установлены `openspec` и `bd`, потому что post-copy bootstrap вызывает `openspec init` и по умолчанию `bd init --stealth`.

```bash
npm install -g @fission-ai/openspec@latest
```

3. Если в вопросах Copier выбрать `git init = no`, beads в интерактивном сценарии будет автоматически отключен. Для уже существующего git-репозитория beads можно явно включить через `-d init_beads=true`.
4. Настройте команды окружения на базе `env/wsl.example.json` или `env/windows-executor.example.json`.
5. При необходимости добавьте свой adapter в `scripts/adapters/`.
6. Обновите `automation/context/project-map.md` под предметную область проекта.
7. Создайте первый change в `openspec/changes/`.

### Команда `new-1c-project`

- Versioned source helper-скрипта лежит в `tooling/new-1c-project` репозитория шаблона
- Рекомендуемое место установки: `~/.local/bin/new-1c-project`
- Убедитесь, что `~/.local/bin` находится в `PATH`
- В `~/.local/bin/new-1c-project` достаточно держать thin-wrapper или symlink на versioned source
- Если локальный helper не установлен, прямой вызов `copier copy ...` остается каноническим способом создания проекта

Простейший сценарий установки через symlink из корня репозитория шаблона:

```bash
install -d ~/.local/bin
ln -sf "$(pwd)/tooling/new-1c-project" ~/.local/bin/new-1c-project
```

После этого проверьте:

```bash
new-1c-project --help
```

### Команда `update-1c-project`

- Versioned source helper-скрипта лежит в `tooling/update-1c-project` репозитория шаблона
- Рекомендуемое место установки: `~/.local/bin/update-1c-project`
- В `~/.local/bin/update-1c-project` достаточно держать thin-wrapper или symlink на versioned source
- Helper ожидает, что конечный проект уже является git-репозиторием и содержит `.copier-answers.yml`

Простейший сценарий установки через symlink из корня репозитория шаблона:

```bash
install -d ~/.local/bin
ln -sf "$(pwd)/tooling/update-1c-project" ~/.local/bin/update-1c-project
```

После этого проверьте:

```bash
update-1c-project --help
```

## Обновление Сгенерированного Проекта От Шаблона

Чтобы конечный проект можно было обновлять после изменений шаблона:

- создавайте проект из Git-репозитория шаблона или из локального template-repo, который тоже находится в Git;
- публикуйте изменения шаблона через commit/tag, а не только через незакоммиченные локальные файлы;
- храните `.copier-answers.yml` в конечном репозитории;
- запускайте update из чистого git worktree.

Канонические entrypoint-скрипты в сгенерированном проекте:

```bash
make template-check-update
make template-update
```

Или напрямую:

```bash
./scripts/template/check-update.sh
./scripts/template/update-template.sh
copier update --trust --defaults
update-1c-project /path/to/generated-project --vcs-ref v0.1.1
```

`template-update` обновляет файлы шаблона и refresh-ит managed-блок в `AGENTS.md`, не переинициализируя `openspec`, `git` и `bd`.

## Make targets

- `make help`
- `make qa`
- `make analyze-bsl`
- `make format-bsl`
- `make test-xunit`
- `make test-bdd`
- `make smoke`
- `make export-context`
- `make verify-traceability`
- `make template-check-update`
- `make template-update`

## Что этот шаблон не делает автоматически

- не парсит `env/*.json` сам по себе;
- не выбирает платформу 1С за вас;
- не навязывает `vrunner`, EDT или конкретный CI;
- не коммитит локальную beads-базу в Git;
- не подменяет `bd` markdown-трекерами задач;
- не содержит готовых секретов, строк подключений и учетных данных.

Шаблон задает контракт структуры и точек входа. Конкретные команды запуска вы заполняете под свой контур.
