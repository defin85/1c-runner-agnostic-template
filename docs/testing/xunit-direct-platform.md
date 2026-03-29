# xUnit Direct-Platform Contour

Этот документ описывает template-managed operator-local xUnit contour, который generated repositories получают из шаблона.
Outer launcher boundary остаётся общей: `./scripts/test/run-xunit.sh`.

## Канонический запуск

1. Скопируйте direct-platform example profile в local-private runtime profile.
2. Пропишите реальный `capabilities.xunit.addRoot` с `xddTestRunner.epf`.
3. Запускайте contour через launcher boundary:

```bash
./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run
```

## Канонический TDD loop

Для обычного add/modify/untracked цикла по `src/cf` используйте:

```bash
./scripts/test/tdd-xunit.sh --profile env/local.json --run-root /tmp/tdd-xunit-run
```

Wrapper делает:

1. `./scripts/platform/load-diff-src.sh`
2. `./scripts/platform/update-db.sh`
3. `./scripts/test/run-xunit.sh`

в этом порядке и только если под `src/cf` есть git-backed изменения, которые diff bridge умеет безопасно воспроизвести.

## Fail-Closed Limits

`./scripts/test/tdd-xunit.sh` специально не делает silent fallback на full reload.
Если под `src/cf` есть delete/rename/conflict-style изменения, wrapper завершится ошибкой и попросит использовать manual path:

```bash
./scripts/platform/load-src.sh --profile env/local.json --run-root /tmp/load-src-run
./scripts/platform/update-db.sh --profile env/local.json --run-root /tmp/update-db-run
./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run
```

## Что реально запускается

- launcher entrypoint: `./scripts/test/run-xunit.sh`
- direct-platform runner: `./scripts/test/run-xunit-direct-platform.sh`
- EPF build helper: `./scripts/test/build-xunit-epf.sh`
- local TDD wrapper: `./scripts/test/tdd-xunit.sh`
- shipped harness source: `src/epf/TemplateXUnitHarness`
- starter config: `tests/xunit/smoke.quickstart.json`

## Profile Fields

`capabilities.xunit` в direct-platform profile может использовать:

- `command`: `["./scripts/test/run-xunit-direct-platform.sh"]`
- `addRoot`: operator-local ADD root с `xddTestRunner.epf`
- `harnessSourceDir`: source tree для project-owned harness, по умолчанию template starter `./src/epf/TemplateXUnitHarness`
- `configPath`: optional override для `tests/xunit/smoke.quickstart.json`
- `xddRunTargetRel`: optional fallback target внутри copied ADD root
- `timeoutSeconds`: optional contour timeout

Runner читает launcher-provided `ONEC_*` env contract, если outer launcher уже передал profile metadata и capability run root.
