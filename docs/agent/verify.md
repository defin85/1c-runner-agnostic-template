# Verify

## Baseline

Первый lightweight verify path:

```bash
make agent-verify
```

Этот contour должен подтверждать:

- валидность OpenSpec;
- layout traceability;
- целостность skill bindings;
- целостность agent-facing docs и live context;
- Python-код проходит `ruff check`, `ruff format --check` и basedpyright (режим `standard`, без baseline);
- быстрый набор pytest-тестов `tests/python` и smoke `tests/smoke/python-type-checking-contract.sh`, `tests/smoke/python-ruff-config-contract.sh`.

Baseline intentionally не требует:

- licensed 1C runtime;
- BSL Language Server / Java;
- secret runtime profiles.

## Python Quality Contour

Python-инструменты берутся только из окружения `uv` проекта (`uv run --locked ...`): версии ruff, basedpyright и pytest закреплены в `pyproject.toml` и `uv.lock`. Глобально установленные ruff/basedpyright/pytest не используются: без `uv` цели завершаются ошибкой с подсказкой установки ([docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)). Первый запуск сам создаёт `.venv` через `uv run`.

```bash
make verify-python-lint     # ruff check . && ruff format --check .   (Windows: ./make.ps1 verify-python-lint)
make verify-types           # scripts/qa/type-check.sh -> basedpyright  (Windows: ./make.ps1 verify-types)
make verify-python-tests    # полный pytest по tests/python            (Windows: ./make.ps1 verify-python-tests)
make verify-python-tests ARGS="--fast"   # быстрый набор, который запускает agent-verify
bash tests/smoke/python-type-checking-contract.sh
bash tests/smoke/python-ruff-config-contract.sh
```

- Настройки: `ruff.toml`, который через `extend` подключает базовые правила `scripts/qa/ruff-base.toml` (`E4,E7,E9,F,B,I,UP`, `py312`, длина строки 120), и `pyrightconfig.json`, который через `extends` подключает базовые правила `scripts/qa/pyright-base.json` (`standard`) и задаёт только `include`/`exclude`. Каталог `automation/vendor/` исключён из обеих проверок.
- `pyproject.toml`, `uv.lock`, `requirements-dev.txt`, `pyrightconfig.json` и `ruff.toml` в созданном проекте seed-once и project-owned (Р15, Р18); `make verify-python-lint` до запуска `ruff` проверяет, что `ruff.toml` расширяет базу и не отключает её правила для файлов шаблона, и что `ruff` установлен в окружении `uv`; проверка типов требует пины `ruff`, `basedpyright`, `pytest` не ниже минимальных версий шаблона и печатает команду исправления. Подробности: [docs/template-maintenance.md](../template-maintenance.md#project-owned-extension-points).
- Каждый `# noqa` и `# pyright: ignore[...]` содержит причину; правила в конфиге не отключаются.
- Baseline basedpyright запрещён: при наличии `basedpyright-baseline*` или `.basedpyright/baseline*` проверка типов падает. Ошибки исправляются кодом.
- Python-файл вне корней `include` из `pyrightconfig.json` делает проверку типов неуспешной: добавьте корень в `include` или осознанно в `exclude`; файлы и каталоги из `exclude` проверка не считает неклассифицированными.
- `requirements-dev.txt` — производный export из `uv.lock`; проверка типов сравнивает его с `uv export` и при расхождении печатает команду перегенерации. После `uv lock` выполните:

  ```bash
  uv export --locked --format requirements-txt --no-hashes --no-emit-project --no-annotate --output-file requirements-dev.txt
  ```

- `make agent-verify` запускает быстрый набор pytest: весь `tests/python`, кроме самых долгих наборов операций metadata CLI (список `PYTEST_SLOW_FILES` в `scripts/python/type_checking.py`). Полный набор (несколько минут) запускается в CI в job `fixture` и локально через `make verify-python-tests`.

## Local GitHub Actions Preflight

Перед push в GitHub source repo также поддерживает локальный прогон воспроизводимого CI contour через `act`:

```bash
make act-preflight
```

Что именно покрывает этот path:

- Linux job `static`;
- Linux job `fixture`, который transitively включает `static` через `needs`;
- non-interactive `act` config с явным container image mapping.

Что deliberately не покрывается локально:

- `windows-latest` matrix jobs;
- `workflow_dispatch` runtime contour на self-hosted 1C runner.

Для быстрой проверки wiring без запуска контейнеров:

```bash
./scripts/qa/act-preflight.sh --dryrun
```

## Fixture Contour

Если меняются bootstrap, copier delivery, agent overlays или template packaging, переходите к fixture/smoke проверкам:

```bash
bash tests/smoke/bootstrap-agents-overlay.sh
bash tests/smoke/copier-update-ready.sh
bash tests/smoke/template-release-workflow.sh
bash tests/smoke/project-extension-points.sh
```

`make agent-verify` после базовых проверок выполняет project-owned шаги из `scripts/qa/agent-verify.d/`, если каталог есть. В source repo шаблона этого каталога нет. Контракт точек расширения generated project (`Makefile.project`, `make.project.ps1`, `scripts/qa/agent-verify.d/`, проектный блок `.gitignore`/`.gitattributes`/`.contextignore`) описан в [docs/template-maintenance.md](../template-maintenance.md#project-owned-extension-points).

Если меняются skills или их пути, отдельно проверьте контракт путей в `SKILL.md`:

```bash
bash tests/smoke/skill-bindings-paths.sh
```

`check-skill-bindings` требует, чтобы пути репозитория, упомянутые в `SKILL.md` (`scripts/`, `docs/`, `tests/`, `automation/`, `env/` и т.д.), существовали. Допускаются glob-шаблоны, git-ignored operator-local файлы и пути необязательных модулей, пока модуль не материализован (`scripts/python/optional_modules.py`).

## Runtime Contour

Если задача затрагивает launcher behavior, profile contract или adapter runtime, переходите к runtime smoke:

```bash
bash tests/smoke/runtime-capability-contract.sh
bash tests/smoke/runtime-doctor-contract.sh
bash tests/smoke/yaxunit-contour-contract.sh
bash tests/smoke/yaxunit-warm-rpc-contour-contract.sh
```

И к более узким smoke для конкретного contour, если он затронут.

## Heavier QA Contours

`make qa` остаётся более широким и более тяжёлым contour, потому что включает BSL-oriented checks.
Для нового агента это не первый шаг, а следующий слой после baseline.
