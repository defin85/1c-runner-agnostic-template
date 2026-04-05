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
```

## Runtime Contour

Если задача затрагивает launcher behavior, profile contract или adapter runtime, переходите к runtime smoke:

```bash
bash tests/smoke/runtime-capability-contract.sh
bash tests/smoke/runtime-doctor-contract.sh
bash tests/smoke/template-xunit-contour-contract.sh
bash tests/smoke/tdd-xunit-wrapper-contract.sh
```

И к более узким smoke для конкретного contour, если он затронут.

## Heavier QA Contours

`make qa` остаётся более широким и более тяжёлым contour, потому что включает BSL-oriented checks.
Для нового агента это не первый шаг, а следующий слой после baseline.
