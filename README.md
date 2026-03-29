# 1c-runner-agnostic-template

Исходный репозиторий шаблона для 1С-проектов.
Здесь живут reusable runtime/test/QA contract, bootstrap/update hooks, agent-facing docs и smoke-контуры поставки шаблона.

Если вам нужен authoritative onboarding для текущего репозитория, начинайте с [docs/agent/index.md](docs/agent/index.md).
Этот маршрут отвечает на три базовых вопроса:

- что это за репозиторий;
- чем source repo отличается от generated project;
- какой verify contour запускать первым.

Generated projects получают собственные root entrypoint-ы при `copier copy`:

- project-first `README.md`;
- bootstrap overlay в `AGENTS.md`;
- project-owned `automation/context/project-map.md` и `openspec/project.md`;
- generated-project docs вроде `docs/agent/generated-project-index.md` и `docs/agent/generated-project-verification.md`.

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

Для agent-facing navigation используйте [docs/agent/index.md](docs/agent/index.md).
В source repo корневой [AGENTS.md](AGENTS.md) остаётся коротким entrypoint; в generated project этот слой дополняется bootstrap overlay.

## Структура

```text
.
├── .claude/
├── .agents/
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
- `.agents/` — project-scoped Codex skills для повторяемых workflow.
- `.claude/` — project-scoped Claude settings и skills.
- `.github/` — CI workflows, поставляемые шаблоном.
- `.codex/` — project-local Codex config template, включая пример `config.toml` для MCP servers.
- `docs/` — ADR, архитектурные заметки, эксплуатационная документация.
- `.beads/` — локальная issue-база beads, создается bootstrap-скриптом и скрывается из Git.

## Agent Docs

System of record для нового агента находится в [docs/agent/index.md](docs/agent/index.md).

В template source repo этот индекс объясняет устройство самого шаблона.
Generated projects получают отдельный стартовый слой в [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) и verification matrix в [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md).
Если high-level overview из `README.md` и `openspec/project.md` кажется недостаточным или частично дублирующимся, приоритет для onboarding у `docs/agent/`.

Минимальный маршрут discovery такой:

- [docs/agent/index.md](docs/agent/index.md) — куда идти за authoritative guidance;
- [docs/agent/architecture.md](docs/agent/architecture.md) — карта top-level зон repo;
- [docs/agent/source-vs-generated.md](docs/agent/source-vs-generated.md) — граница между template source repo и generated project;
- [docs/agent/verify.md](docs/agent/verify.md) — baseline/fixture/runtime контуры проверки;
- [docs/agent/review.md](docs/agent/review.md) — repo-specific review expectations;
- [docs/template-maintenance.md](docs/template-maintenance.md) — isolated guide для versioned overlay maintenance;
- [docs/exec-plans/README.md](docs/exec-plans/README.md) — versioned место для long-running execution plans.

## Принцип запуска

В проекте нет жесткой привязки к одному runner.

Все запускатели идут через стабильные entrypoint-скрипты:

- `./scripts/platform/create-ib.sh`
- `./scripts/platform/dump-src.sh`
- `./scripts/platform/load-src.sh`
- `./scripts/platform/load-diff-src.sh`
- `./scripts/platform/load-task-src.sh`
- `./scripts/platform/update-db.sh`
- `./scripts/platform/diff-src.sh`
- `./scripts/platform/publish-http.sh`
- `./scripts/diag/doctor.sh`
- `./scripts/test/run-xunit.sh`
- `./scripts/test/run-xunit-direct-platform.sh`
- `./scripts/test/build-xunit-epf.sh`
- `./scripts/test/tdd-xunit.sh`
- `./scripts/test/run-bdd.sh`
- `./scripts/test/run-smoke.sh`
- `./scripts/qa/analyze-bsl.sh`
- `./scripts/qa/format-bsl.sh`

Backend выбирается через `RUNNER_ADAPTER`:

- `direct-platform`
- `remote-windows`
- `vrunner`

Для core runtime capabilities backend 1C toolchain дополнительно выбирается через per-capability `driver`:

- default: `designer`
- opt-in: `ibcmd` только вместе с `RUNNER_ADAPTER=direct-platform`
- `env/local.example.json` показывает mixed-profile c `ibcmd.runtimeMode=file-infobase`, чтобы partial import был готов из checked-in preset
- `env/wsl.example.json` показывает canonical WSL/Linux contour с `platform.xvfb` и `platform.ldPreload`, чтобы локальные `1cv8`/`1cv8c` запускались без мигания GUI-окон на хосте и с repo-owned linker compatibility contour
- direct-platform example profiles также уже wires template-managed xUnit contour через `./scripts/test/run-xunit-direct-platform.sh`; operator-local `addRoot` нужно заменить на реальный ADD path

Параметры подключения к ИБ, `ibcmd` coordinates и platform paths задаются через structured runtime profile. Для project-specific contour допускаются `command`-массивы в секции `capabilities`.

### Runtime Profile Contract

Канонический способ конфигурации launcher-скриптов теперь это runtime profile JSON:

- versioned examples лежат в `env/*.example.json`;
- локальные канонические профили можно хранить только в `env/local.json`, `env/wsl.json`, `env/ci.json`, `env/windows-executor.json`, и они уже исключены из Git;
- ad-hoc и machine-specific profiles нужно складывать в `env/.local/*.json`;
- любой capability entrypoint принимает `--profile <file>` и `--run-root <dir>`;
- если `--profile` не указан, скрипт пытается использовать `ONEC_PROFILE`, затем `env/local.json`;
- каждый capability entrypoint пишет `summary.json`, `stdout.log` и `stderr.log` в `run-root`.
- `schemaVersion: 1` больше не поддерживается.

`doctor` дополнительно предупреждает о layout drift, если в корне `env/` появляются локальные `*.json` вне канонического allowlist. Это warning-only check: он не меняет default resolution и не блокирует runtime launch сам по себе.

Базовые поля profile:

- `schemaVersion`
- `profileName`
- `runnerAdapter`
- `platform`
- `infobase`
- `capabilities`

Если хотя бы один core capability использует `driver=ibcmd`, profile также задаёт `platform.ibcmdPath` и блок `ibcmd` с явным `runtimeMode` и `serverAccess`.
Для WSL/Linux GUI isolation profile может дополнительно задавать `platform.xvfb.enabled=true` и `platform.xvfb.serverArgs` как массив токенов для `xvfb-run`.
Для WSL/Arch Linux linker compatibility profile может дополнительно задавать `platform.ldPreload.enabled=true` и `platform.ldPreload.libraries` как массив абсолютных library paths. Launcher сам собирает `LD_PRELOAD` и не требует ad-hoc `env LD_PRELOAD=... ./scripts/...` префиксов.

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
- `load-diff-src`
- `load-task-src`
- `update-db`
- `diff-src`
- `run-xunit`
- `tdd-xunit`
- `run-bdd`
- `run-smoke`
- `doctor`

Пример:

```bash
cp env/local.example.json env/local.json
export ONEC_IBCMD_PASSWORD='...'
./scripts/diag/doctor.sh --profile env/local.json
./scripts/platform/load-src.sh --profile env/local.json --run-root /tmp/load-src-run
./scripts/platform/load-src.sh --profile env/local.json --files "Catalogs/Items.xml,Forms/List.xml"
./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run
./scripts/platform/load-task-src.sh --profile env/local.json --bead demo.1 --run-root /tmp/load-task-src-run
```

Для WSL/Linux isolated GUI launches:

```bash
cp env/wsl.example.json env/wsl.json
./scripts/diag/doctor.sh --profile env/wsl.json
./scripts/platform/dump-src.sh --profile env/wsl.json --run-root /tmp/wsl-dump-run
```

Для временных локальных контуров:

```bash
cp env/local.example.json env/.local/develop.json
./scripts/diag/doctor.sh --profile env/.local/develop.json
```

Если этот contour использует `platform.ldPreload`, `doctor` fail-closed завершится до старта 1С, если одна из library paths отсутствует или задана не как абсолютный путь.

Важно:

- `driver` и `command` нельзя смешивать в одной capability;
- checked-in `env/local.example.json` уже wired для partial import через `loadSrc.driver=ibcmd`;
- `load-diff-src` строит git-backed selection внутри `src/cf` и делегирует actual import в `load-src --files`;
- `load-task-src` строит committed task selection по trailers `Bead:` / `Work-Item:` или по explicit `--range` и тоже делегирует actual import в `load-src --files`;
- `summary.json` для `create-ib`, `dump-src`, `load-src`, `update-db` теперь отражает выбранный `driver`;
- direct-platform contour с `platform.xvfb.enabled=true` требует локальные `xvfb-run` и `xauth`, а capability/doctor summary публикуют structured `adapter_context`;
- direct-platform contour с `platform.ldPreload.enabled=true` требует валидные absolute library paths, а capability/doctor summary публикуют structured `adapter_context.ld_preload` без сырого `LD_PRELOAD=` shell prefix;
- canonical XML source-tree format для `ibcmd` это hierarchical.
- canonical examples для `ibcmd` modes разложены так:
  - `env/wsl.example.json` -> `standalone-server`
  - `env/local.example.json` -> `file-infobase`
  - `env/ci.example.json` -> `dbms-infobase`
- `dbms-infobase` является safety-sensitive contour и не считается blanket-safe для live cluster-managed DB без operator-owned isolation.

### Project-Scoped Skills

Шаблон поставляет project-scoped skills в двух packaging surfaces:

- `.agents/skills/` для Codex;
- `.claude/skills/` для Claude.

- Skills являются thin-wrapper над repo-owned scripts и не должны дублировать runtime logic.
- Каноническая таблица соответствия `intent -> Codex skill -> Claude skill -> repo entrypoint` лежит в `.agents/skills/README.md`.
- `.claude/skills/README.md` повторяет тот же mapping для Claude-facing navigation.
- Базовая project policy для Claude находится в `.claude/settings.json`.
- Первый lightweight verification path для repo/doc/tooling changes: `make agent-verify`.

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
OpenSpec-артефакты самого репозитория шаблона (`openspec/`, корневые `AGENTS.md`/`CLAUDE.md`, `.claude/commands/openspec`) не рендерятся в конечный проект и не должны перетирать его собственный OpenSpec ни при bootstrap, ни при compatibility-migration через `copier update`.
Шаблон сохраняет `.copier-answers.yml` как bootstrap provenance, а ongoing updates после первой миграции идут через versioned overlay path.

2. Убедитесь, что установлены `openspec` и `bd`, потому что post-copy bootstrap вызывает `openspec init` и по умолчанию `bd init --stealth`.

```bash
npm install -g @fission-ai/openspec@latest
```

3. Если в вопросах Copier выбрать `git init = no`, beads в интерактивном сценарии будет автоматически отключен. Для уже существующего git-репозитория beads можно явно включить через `-d init_beads=true`.
4. Настройте команды окружения на базе `env/wsl.example.json`, `env/local.example.json` или `env/windows-executor.example.json`.
5. При необходимости добавьте свой adapter в `scripts/adapters/`.
6. Если нужен live project context, возьмите skeleton files из `automation/context/templates/` и создайте на их основе свои project-specific context artifacts.
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
- Helper ожидает, что конечный проект уже является generated repo и содержит `scripts/template/update-template.sh`

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
- храните `.copier-answers.yml` и `.template-overlay-version` в конечном репозитории;
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
update-1c-project /path/to/generated-project --vcs-ref v0.1.1
```

`template-check-update` сверяет `.template-overlay-version` с latest tagged release шаблона или с явно переданным `--vcs-ref`.
`template-update` materialize-ит выбранный template ref, обновляет только manifest-declared template-managed assets, refresh-ит generated README router и managed-блок в `AGENTS.md`, при необходимости восстанавливает missing root entrypoint files, удаляет legacy `src/cf/AGENTS.md` и `src/cf/README.md`, если они остались от старых template release, и не переинициализирует `openspec`, `git` и `bd`.

## Make targets

- `make help`
- `make agent-verify`
- `make qa`
- `make analyze-bsl`
- `make format-bsl`
- `make check-agent-docs`
- `make check-skill-bindings`
- `make check-overlay-manifest`
- `make create-ib`
- `make dump-src`
- `make load-src`
- `make update-db`
- `make diff-src`
- `make doctor`
- `make test-xunit`
- `make tdd-xunit`
- `make test-bdd`
- `make smoke`
- `make export-context`
- `make export-context-preview`
- `make export-context-check`
- `make export-context-write`
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
