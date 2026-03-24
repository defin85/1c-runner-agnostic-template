# Generated Project Verification

Этот документ делит проверки generated project на три слоя: `safe local`, `profile-required`, `provisioned/self-hosted 1C`.

## Safe Local

Эти команды не требуют 1С runtime profile и не должны менять checked-in артефакты без явного `--write`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `make agent-verify` | Базовая проверка docs, OpenSpec, skills и context contract | shell + repo tooling | нет | stdout/stderr процесса |
| `make export-context-preview` | Посмотреть generated-derived inventory без записи | shell-only | нет | preview в stdout |
| `make export-context-check` | Проверить свежесть generated-derived/context files | shell-only | нет | exit code |

Минимальный no-1C baseline:

```bash
make agent-verify
make export-context-check
```

## Profile-Required

Эти команды требуют валидный runtime profile и обычно пишут run artifacts в указанный `--run-root`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | Проверка readiness runtime profile | 1С binaries и profile | пишет только run-root | `summary.json`, `stdout.log`, `stderr.log` |
| `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | Короткий runtime smoke contour | подготовленный profile | пишет только run-root | run-root logs и summary |
| `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | xUnit contour | подготовленный profile | пишет только run-root | run-root logs и summary |
| `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | BDD contour | подготовленный profile | пишет только run-root | run-root logs и summary |

## Provisioned / Self-Hosted 1C

Эти команды требуют provisioned infobase или operator-owned runtime contour. Перед запуском проверьте проектные ограничения и секреты.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `./scripts/platform/create-ib.sh --profile env/local.json --run-root /tmp/create-ib-run` | Создание ИБ | runtime + writable target | меняет runtime target | run-root logs и summary |
| `./scripts/platform/load-src.sh --profile env/local.json --run-root /tmp/load-src-run` | Загрузка source tree в ИБ | runtime + prepared infobase | меняет ИБ | run-root logs и summary |
| `./scripts/platform/update-db.sh --profile env/local.json --run-root /tmp/update-db-run` | Обновление DB configuration | runtime + prepared infobase | меняет ИБ | run-root logs и summary |
| `./scripts/platform/dump-src.sh --profile env/local.json --run-root /tmp/dump-src-run` | Выгрузка исходников | runtime + prepared infobase | меняет target source tree или run-root по контракту capability | run-root logs и summary |

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
