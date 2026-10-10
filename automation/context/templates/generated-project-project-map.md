# Generated Project Map Starter

Этот файл показывает структуру project-owned карты generated repo.
Живой curated контекст должен храниться в `automation/context/project-map.md`.

## Обязательные секции

- repository identity;
- repo-derived snapshot;
- known source roots;
- ownership model;
- canonical entrypoints;
- runtime support truth;
- immediate routers;
- next enrichment steps.

## Что уточнять в project-owned карте

- бизнес-домен и ключевые bounded contexts;
- реальные metadata entrypoint-ы;
- HTTP services, scheduled jobs, forms, external processors и extensions;
- review / env / skills / exec-plan routers, если команда меняет стартовый onboarding;
- ограничения проекта, которые не принадлежат template-managed слою.

## Project-owned точки расширения

- проектные цели `make` и `./make.ps1` — в `Makefile.project` и `make.project.ps1`, а не в template-managed `Makefile`/`make.ps1`;
- проектные шаги `make agent-verify` — в `scripts/qa/agent-verify.d/`;
- проектные строки `.gitignore`, `.gitattributes`, `.contextignore` — только между маркерами project-owned блока;
- Python-окружение проекта — `pyproject.toml`, `uv.lock`, `requirements-dev.txt`, `pyrightconfig.json`, `ruff.toml`: шаблон создаёт их один раз, дальше проект сам добавляет зависимости, корни проверки типов и исключения своих файлов из `ruff`; `pyrightconfig.json` сохраняет `extends` на `scripts/qa/pyright-base.json`, `ruff.toml` — `extend` на `scripts/qa/ruff-base.toml`;
- `template-update` эти пути и блоки не перезаписывает; контракт описан в `docs/template-maintenance.md` (раздел `Project-Owned Extension Points`), а в карте проекта достаточно перечислить, какие точки команда использует и зачем.

## Инструменты разработки шаблона

В карте проекта достаточно указать, какие из этих инструментов команда использует; контракт команд описан в навыках и в runtime support matrix.

- проверка синтаксиса BSL — навык `1c-check-bsl`, цели `check-bsl`, `check-cf-modules`, `analyze-bsl-external`;
- клиент 1С и наблюдение длительных запусков — навыки `1c-run-client` и `1c-observe-run` (`observation.jsonl`, `progress.txt`, `scripts/diag/technological-log.sh`);
- метаданные и формы в XML — навыки `metadata-use`, `metadata-cli-development`, `cfe-form-workflow`, обычные формы — `ordinary-form-workflow`, `prepare-external-artifact`, `v8unpack`;
- справочник стандартов `v8std` — `scripts/tools/v8std-fetch` и `scripts/tools/v8std-search` (только Linux), кеш в `.artifacts/v8std`;
- хранилище артефактов вне checkout — `scripts/artifact-storage`, каталог `<repo>-artifacts` рядом с репозиторием;
- кластер, падения сервера и перенос доработок — навыки `1c-rac-operations`, `1c-linux-crash-diagnostics`, `legacy-customization-port`.

Windows-обёртки этих команд поставляются, но на Windows ещё не запускались.

## Что не смешивать с этим файлом

- compact generated summary из `automation/context/hotspots-summary.generated.md`, если нужна summary-first навигация;
- project-owned code architecture map из `docs/agent/architecture-map.md`, если нужен scenario-driven routing по коду;
- project-owned runtime quick reference из `docs/agent/runtime-quickstart.md`, если нужен короткий runtime digest;
- compact project-aware skill routing из `automation/context/recommended-skills.generated.md`, если нужен first-hour shortlist вместо полного catalog;
- machine-generated inventory из `automation/context/metadata-index.generated.json`;
- project-owned sanctioned profile policy из `automation/context/runtime-profile-policy.json`, если речь про checked-in team-shared presets;
- checked-in runtime truth из `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`;
- машинно-зависимые настройки из `env/local.json`, `env/wsl.json`, `env/.local/*.json`;
- push-only closeout contract, если репозиторий local-only и remote не настроен;
- template maintenance notes, которые уже живут в `docs/template-maintenance.md`.
