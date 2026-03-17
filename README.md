# {{ project_name }}

Шаблон проекта для разработки на 1С по принципам:

- `SDD` (`Spec-Driven Development`) через `OpenSpec`
- `TDD` через `tests/` и `features/`
- `beads` для локального issue-tracking в stealth-режиме
- `LLM-first automation` через `AGENTS.md`, `automation/` и стабильные launcher-скрипты
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
- держать в репозитории явные точки входа для спецификаций, тестов, запуска и локального трекинга.

Правила работы, workflow агента и operational contract находятся в `AGENTS.md`.

## Структура

```text
.
├── .claude/
├── .github/
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
- `.claude/` — project-scoped Claude settings и skills.
- `.github/` — CI workflows, поставляемые шаблоном.
- `.codex/` — project-local Codex config template, включая пример `config.toml` для MCP servers.
- `docs/` — ADR, архитектурные заметки, эксплуатационная документация.
- `.beads/` — локальная issue-база beads, создается bootstrap-скриптом и скрывается из Git.

## Принцип запуска

В проекте нет жесткой привязки к одному runner.

Все запускатели идут через стабильные entrypoint-скрипты:

- `./scripts/platform/create-ib.sh`
- `./scripts/platform/dump-src.sh`
- `./scripts/platform/load-src.sh`
- `./scripts/platform/update-db.sh`
- `./scripts/platform/diff-src.sh`
- `./scripts/platform/publish-http.sh`
- `./scripts/diag/doctor.sh`
- `./scripts/test/run-xunit.sh`
- `./scripts/test/run-bdd.sh`
- `./scripts/test/run-smoke.sh`
- `./scripts/qa/analyze-bsl.sh`
- `./scripts/qa/format-bsl.sh`

Backend выбирается через `RUNNER_ADAPTER`:

- `direct-platform`
- `remote-windows`
- `vrunner`

Параметры подключения к ИБ и platform paths задаются через structured runtime profile. Для project-specific contour допускаются `command`-массивы в секции `capabilities`.

### Runtime Profile Contract

Канонический способ конфигурации launcher-скриптов теперь это runtime profile JSON:

- versioned examples лежат в `env/*.example.json`;
- локальные рабочие профили можно хранить в `env/local.json`, `env/ci.json`, `env/windows-executor.json` и они уже исключены из Git;
- любой capability entrypoint принимает `--profile <file>` и `--run-root <dir>`;
- если `--profile` не указан, скрипт пытается использовать `ONEC_PROFILE`, затем `env/local.json`;
- каждый capability entrypoint пишет `summary.json`, `stdout.log` и `stderr.log` в `run-root`.
- `schemaVersion: 1` больше не поддерживается.

Базовые поля profile:

- `schemaVersion`
- `profileName`
- `runnerAdapter`
- `platform`
- `infobase`
- `capabilities`

Для password-based auth profile хранит не secret value, а имя env var, например `passwordEnv: "ONEC_IB_PASSWORD"`.

Миграция legacy profiles:

```bash
./scripts/template/migrate-runtime-profile-v2.sh env/local.json > /tmp/local.v2.json
```

Подробности: `docs/migrations/runtime-profile-v2.md`.

Минимальный capability set v1:

- `create-ib`
- `dump-src`
- `load-src`
- `update-db`
- `diff-src`
- `run-xunit`
- `run-bdd`
- `run-smoke`
- `doctor`

Пример:

```bash
cp env/local.example.json env/local.json
export ONEC_IB_PASSWORD='...'
./scripts/diag/doctor.sh --profile env/local.json
./scripts/platform/load-src.sh --profile env/local.json --run-root /tmp/load-src-run
```

### Project-Scoped Skills

Шаблон поставляет project-scoped Claude skills в `.claude/skills/`.

- Skills являются thin-wrapper над repo-owned scripts и не должны дублировать runtime logic.
- Таблица соответствия `intent -> skill -> script` лежит в `.claude/skills/README.md`.
- Базовая project policy для Claude находится в `.claude/settings.json`.

Проверка связки skills:

```bash
./scripts/qa/check-skill-bindings.sh
```

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
OpenSpec-артефакты самого репозитория шаблона (`openspec/`, корневые `AGENTS.md`/`CLAUDE.md`, `.claude/commands/openspec`) не рендерятся в конечный проект и не должны перетирать его собственный OpenSpec при `copier update`.
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
- `make check-skill-bindings`
- `make create-ib`
- `make dump-src`
- `make load-src`
- `make update-db`
- `make diff-src`
- `make doctor`
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

## CI Contours

Шаблон поставляет layered CI workflow в `.github/workflows/ci.yml`.

- `static`:
  - shell syntax
  - OpenSpec validation
  - проверка skill bindings
- `fixture`:
  - runtime shell fixtures
  - bootstrap/update smoke
- `runtime`:
  - только `workflow_dispatch`
  - только self-hosted runner с labels `self-hosted`, `linux`, `1c`
  - запускается лишь если в репозитории существует `env/ci.json`

Важно:

- `runtime` contour не рассчитан на shared CI среду без 1С runtime;
- реальные credentials и connection details должны поступать из внешних secrets/local-only config, а не из versioned template files.
