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
- целостность agent-facing docs и live context.

Baseline intentionally не требует:

- licensed 1C runtime;
- BSL Language Server / Java;
- secret runtime profiles.

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
