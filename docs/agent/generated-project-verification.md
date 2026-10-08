# Generated Project Verification

Этот документ делит проверки generated project на три слоя: `safe local`, `profile-required`, `provisioned/self-hosted 1C`.
Runtime profile contract, canonical local profile paths и `local-private` правила описаны в [env/README.md](../../env/README.md).
Sanctioned checked-in team-shared presets описываются в `automation/context/runtime-profile-policy.json`.
Checked-in runtime support truth конкретного generated repo живёт в `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
Короткий project-specific digest для первого runtime-вопроса должен жить в `docs/agent/runtime-quickstart.md`.
Operator-local decision bridge для local-private contour-ов в generated project должен жить в `docs/agent/operator-local-runbook.md`; в source repo его template contract лежит в `automation/context/templates/generated-project-operator-local-runbook.md`.

## Safe Local

Эти команды не требуют 1С runtime profile и не должны менять checked-in артефакты без явного `--write`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `make codex-onboard` | Read-only first screen для новой Codex-сессии | shell-only | нет | stdout |
| `make agent-verify` | Базовая проверка docs, OpenSpec, skills и context contract | shell + repo tooling | нет | stdout/stderr процесса |
| `make template-check-update` | Проверить, доступен ли новый wrapper overlay release | shell + git access к template source | нет | stdout/stderr процесса |
| `make export-context-preview` | Посмотреть generated-derived inventory без записи | shell-only | нет | preview в stdout |
| `make export-context-check` | Проверить свежесть generated-derived/context files | shell-only | нет | exit code |
| `make imported-skills-readiness` | Проверить canonical readiness/bootstrap contract для executable imported compatibility skills | shell + Python/Node detection only | нет | stdout |

Минимальный no-1C baseline:

```bash
make codex-onboard
make agent-verify
make export-context-check
make imported-skills-readiness
```

Windows path использует те же contour ids через `./make.ps1 codex-onboard`, `./make.ps1 agent-verify` и `./make.ps1 export-context-check`.
Для runtime-команд используется тот же формат аргументов: `./make.ps1 doctor --profile env/windows-local.json`, `./make.ps1 load-src --profile env/windows-local.json --run-root .artifacts/load-src` и `./make.ps1 publish-http --profile env/windows-local.json`. WSL и Git Bash для этого пути не требуются.

Optional project-specific baseline extension:

- если `automation/context/runtime-support-matrix.json` объявляет `projectSpecificBaselineExtension`, относитесь к нему как к соседнему project-owned contour, а не к template baseline;
- advertising такого contour-а должно идти через runtime support matrix, `docs/agent/runtime-quickstart.md` и `make codex-onboard`;
- отсутствие extension по умолчанию не делает generated repo “неполным”.

Project-owned шаги самого `agent-verify`:

- проектные проверки без 1С, которые должны входить в `make agent-verify`, кладите в `scripts/qa/agent-verify.d/` (`*.py` для всех ОС, `*.sh` для Linux/macOS, `*.ps1` для Windows);
- шаги выполняются после базовых проверок шаблона в порядке имён файлов, первый отказ останавливает `agent-verify`;
- `template-update` этот каталог не трогает; правила и остальные точки расширения (`Makefile.project`, `make.project.ps1`, проектный блок `.gitignore`/`.gitattributes`/`.contextignore`) описаны в [docs/template-maintenance.md](../template-maintenance.md#project-owned-extension-points).

Python-окружение проекта:

- `make verify-python-lint`, `make verify-types` и быстрый pytest входят в `make agent-verify` и запускают инструменты только через `uv run --locked`; без `uv` они завершаются ошибкой;
- `pyproject.toml`, `uv.lock`, `requirements-dev.txt` и `pyrightconfig.json` принадлежат проекту: добавляйте свои зависимости (`uv add --dev ...`, затем перегенерация `requirements-dev.txt`) и корни проверки типов (`include` в `pyrightconfig.json`); `template-update` их не перезаписывает;
- `pyrightconfig.json` должен сохранять `"extends": "scripts/qa/pyright-base.json"`, режим не ниже `standard` и не отключать правила; минимальные версии `ruff`, `basedpyright`, `pytest` задаёт шаблон. Подробности: [docs/template-maintenance.md](../template-maintenance.md#project-owned-extension-points).

## Инструменты разработки

Эти команды не входят в `make agent-verify`. Статус каждой — в `automation/context/runtime-support-matrix.md` и `.json`.

| Команда (Linux / Windows) | Назначение | Что нужно | Изменяет |
| --- | --- | --- | --- |
| `make check-bsl ARGS="<module.bsl>..."` / `./make.ps1 check-bsl <module.bsl>...` | Синтаксис выбранных модулей одного корня: `static` через `bsl-analyzer-app` и `platform` через компиляцию в ИБ профиля | `bsl-analyzer-app`; для `platform` — `--profile` | конфигурацию ИБ профиля при частичной загрузке модулей; конфигурацию базы данных не обновляет |
| `make check-cf-modules ARGS="--profile env/local.json <module.bsl>..."` / `./make.ps1 check-cf-modules` | Designer `/CheckModules` после частичной загрузки модулей основной конфигурации | Designer-ready профиль | конфигурацию ИБ профиля, без обновления конфигурации базы данных |
| `make analyze-bsl-external ARGS="--all-managed"` / `./make.ps1 analyze-bsl-external --all-managed` | Статическая проверка модулей EPF/ERF вместе с основной конфигурацией | `bsl-analyzer-app` и выгрузка `src/cf` | ничего |
| `make run-client ARGS="start --profile env/local.json --run-root <dir>"` / `./make.ps1 run-client start --profile env/windows-local.json` | Открыть клиент ИБ профиля, дождаться завершения, остановить | профиль; на Linux `platform.xpra.enabled=true` | только `--run-root`; `screenshot`, `key`, `click` — только Linux |
| `./scripts/diag/technological-log.sh status` / `./scripts/diag/technological-log.ps1 status` | Состояние и восстановление технологического журнала наблюдаемого запуска | доступный на запись `logcfg.xml` платформы | `logcfg.xml` только на время одного запуска |
| `make artifact-storage ARGS="status"` / `./make.ps1 artifact-storage status` | Хранилище прогонов вне checkout с лимитами размера и свободного места | Python 3.12+ | каталог `<repo>-artifacts` рядом с репозиторием |

- Итог `синтаксис: не проверен` у `check-bsl` и код 3 у `analyze-bsl-external` означают, что проверка не выполнена. Это не успех.
- Каждый наблюдаемый запуск 1С пишет в свой `--run-root` файлы `observation.jsonl`, `progress.txt` и раздел `observation` в `summary.json`; разбор — по навыку `1c-observe-run`.
- Справочник стандартов: `scripts/tools/v8std-fetch` и `scripts/tools/v8std-search` (только Linux), кеш в `.artifacts/v8std` или `V8STD_CACHE_ROOT`.
- Windows-обёртки команд из таблицы поставляются, но на Windows ещё не запускались. До первого запуска на Windows считайте этот путь непроверенным; matrix не содержит для него живого доказательства.

## Imported Compatibility Skills

Executable imported compatibility skills не должны использовать raw helper traceback как primary UX для missing Python/Node dependencies.

Canonical readiness path:

```bash
make imported-skills-readiness
./scripts/skills/run-imported-skill.sh --readiness
```

Что ожидается:

- команда печатает representative readiness status для Python-backed, Node-backed, reference-only и native-alias imported skills;
- если Python-backed или Node-backed runtime не ready, вывод остаётся actionable и указывает на bootstrap path вместо helper stack trace;
- full catalog остаётся в `.agents/skills/README.md`, а compact first-hour routing идёт через `automation/context/recommended-skills.generated.md`;
- representative help-check можно запускать как `./scripts/skills/run-imported-skill.sh cf-edit --help` и `./scripts/skills/run-imported-skill.sh web-test --help`, но missing dependencies должны завершаться fail-closed с readiness guidance, а не с vendored traceback.

## Profile-Required

Эти команды требуют валидный runtime profile и обычно пишут run artifacts в указанный `--run-root`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | Проверка readiness runtime profile | 1С binaries и profile | пишет только run-root | `summary.json`, `stdout.log`, `stderr.log` |
| `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | Короткий runtime smoke contour | подготовленный profile | пишет только run-root | run-root logs и summary |
| `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | BDD contour | подготовленный profile | пишет только run-root | run-root logs и summary |

Важно:

- shared runtime truth ищите сначала в `automation/context/runtime-support-matrix.md` / `.json`, а не в ignored local-private profiles;
- если contour отмечен как `operator-local`, в generated project первым project-owned bridge должен быть `docs/agent/operator-local-runbook.md`, а в source repo смотрите `automation/context/templates/generated-project-operator-local-runbook.md`;
- если sanctioned checked-in profile ещё не wired project-specific contour, используйте `unsupportedReason`, а не `echo TODO`;
- если sanctioned checked-in profile всё же использует `command`, он должен запускать прямой repo-owned entrypoint вроде `./scripts/...` или `make <target>`, а не shell-wrapper / inline / no-op success command;
- repo-owned entrypoint может опираться на launcher-provided `ONEC_*` env contract из [env/README.md](../../env/README.md), чтобы использовать `--run-root`, profile path и capability metadata без повторной обвязки launcher-а;
- такой contour завершится fail-closed и должен считаться `unsupported`, а не зелёной проверкой;
- contour, живущий только через ignored local-private profile, должен быть классифицирован как `operator-local` в runtime support matrix и не должен маскироваться под shared baseline-ready truth.

## Provisioned / Self-Hosted 1C

Эти команды требуют provisioned infobase или operator-owned runtime contour. Перед запуском проверьте проектные ограничения и секреты.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `./scripts/platform/create-ib.sh --profile env/local.json --run-root /tmp/create-ib-run` | Создание ИБ | runtime + writable target | меняет runtime target | run-root logs и summary |
| `./scripts/platform/load-src.sh --profile env/local.json --run-root /tmp/load-src-run` | Загрузка source tree в ИБ | runtime + prepared infobase | меняет ИБ | run-root logs и summary |
| `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` | Загрузка только текущего git-backed diff внутри `src/cf` | runtime + prepared infobase + git worktree | меняет ИБ только через delegated `load-src --files` | wrapper run-root logs и delegated `load-src` summary |
| `./scripts/platform/load-task-src.sh --profile env/local.json --work-item 93984 --run-root /tmp/load-task-src-run` | Загрузка уже закомиченного scope задачи по `Work-Item:` или `--range` | runtime + prepared infobase + git history с canonical trailers или явным revset | меняет ИБ только через delegated `load-src --files` | wrapper run-root logs и delegated `load-src` summary |
| `./scripts/platform/update-db.sh --profile env/local.json --run-root /tmp/update-db-run` | Обновление DB configuration | runtime + prepared infobase | меняет ИБ | run-root logs и summary |
| `./scripts/platform/dump-src.sh --profile env/local.json --run-root /tmp/dump-src-run` | Выгрузка исходников | runtime + prepared infobase | меняет target source tree или run-root по контракту capability | run-root logs и summary |
| `./scripts/platform/configure-cfe-runtime-flags.sh --profile env/local.json --extension <name>` | Флаги расширения: безопасный режим, защита от опасных действий, активность, профиль безопасности | runtime + ИБ с расширением | меняет свойства расширения в ИБ | run-root logs и summary |
| `./scripts/platform/manage-cfe.sh <action> --profile env/local.json [--extension <name>]` | Управление расширениями: `list`, `dump`, `import`, `load`, `save`, `apply`, `activate`, `deactivate`, `delete` | runtime + prepared infobase | меняет ИБ, кроме `list`, `dump`, `save` | run-root logs и summary |

### Опции одного запуска

Опции меняют только текущий запуск; профиль остаётся прежним. Флаг, который capability не поддерживает, отклоняется как неизвестный аргумент.

| Capability | Опция | Поведение |
| --- | --- | --- |
| `load-src` | `--source-dir <dir>` | загружает из указанного каталога вместо `capabilities.loadSrc.sourceDir` |
| `load-src` | `--override-unsupported-profile` | разово снимает `capabilities.loadSrc.unsupportedReason`; только с `--files`, явным `--run-root` и для профиля из `unsupportedOverride.loadSrc.allowedProfiles` в `automation/context/runtime-profile-policy.json`; причина пишется в `summary.json` → `unsupported_override` |
| `dump-src` | `--output-dir <dir>` | выгружает в указанный каталог вместо `capabilities.dumpSrc.outputDir` |
| `dump-src` | `--info-only` | только `ConfigDumpInfo.xml` через `ibcmd config export info`; нужен драйвер `ibcmd` |
| `update-db` | `--vendor-cf <file.cf>` | Designer `/UpdateCfg` из CF поставщика и `/UpdateDBCfg`; только локальная платформа или `remote-windows`, нужен `--run-root` для `designer-out.log` |
| `configure-cfe-runtime-flags` | `--safe-mode yes\|no`, `--unsafe-action-protection yes\|no` | по умолчанию оба `no` |
| `configure-cfe-runtime-flags` | `--active yes\|no`, `--security-profile-name <name>`, `--clear-security-profile` | последние два флага взаимоисключающие; `--clear-security-profile` передаёт пустое имя профиля |
| `manage-cfe` | `--output <dir>` (`dump`), `--source <dir>` (`import`, с `Configuration.xml`), `--file <file>` (`load`, `save`) | обязательны для своих действий и отклоняются для остальных |
| `manage-cfe` | `--driver designer` или `--via-designer` | `import` и `apply` через Designer (`/LoadConfigFromFiles` или `/UpdateDBCfg`) с `-Extension <name>` и журналом `designer.out.log` в run-root |
| `manage-cfe` | `--list-file <file>` | частичный Designer `import`: относительные пути внутри `--source`, по одному в строке |

### Поля профиля для этих сценариев

- `infobase.auth.mode`: `os` или `none` (ИБ без пользователей, аргументы авторизации не передаются).
- `ibcmd.auth.mode`: `user-password` (по умолчанию) или `none`.
- `ibcmd.locale`: локаль `ibcmd infobase create` и регистрации в кластере.
- `capabilities.dumpSrc.sourceFile`: выгрузка из файла `.cf` вместо ИБ (`--file=`); не сочетается с `--info-only`.
- `capabilities.createIb.registerInCluster: true`: после `create-ib` ИБ регистрируется через `rac infobase create` с запретом регламентных заданий. Нужны `infobase.mode=client-server`, `ibcmd.runtimeMode=dbms-infobase`, `platform.racPath`, `cluster.ras`, `infobase.ref`; при `clusterAdmin.user` — `clusterAdmin.passwordEnv`. Уже зарегистрированная ИБ с тем же именем не перезаписывается; итог — в `summary.json` → `registration`.
- `unsupportedOverride.<capabilityKey>.allowedProfiles` в `automation/context/runtime-profile-policy.json`: список расходуемых профилей `env/<name>.json`, для которых разрешён `--override-unsupported-profile`.

## Context Refresh

`./scripts/llm/export-context.sh` по умолчанию не пишет в репозиторий.
Для refresh generated-derived inventory используйте явный write path:

```bash
./scripts/llm/export-context.sh --write
```

Если команда нужна только для инспекции, используйте:

```bash
./scripts/llm/export-context.sh --help
./scripts/llm/export-context.sh --preview
./scripts/llm/export-context.sh --check
```
