# Generated Project Verification

Этот документ делит проверки generated project на три слоя: `safe local`, `profile-required`, `provisioned/self-hosted 1C`.
Runtime profile contract, canonical local profile paths и `local-private` правила описаны в [env/README.md](../../env/README.md).
Sanctioned checked-in team-shared presets описываются в `automation/context/runtime-profile-policy.json`.
Checked-in runtime support truth конкретного generated repo живёт в `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
Короткий project-specific digest для первого runtime-вопроса должен жить в `docs/agent/runtime-quickstart.md`.

## Safe Local

Эти команды не требуют 1С runtime profile и не должны менять checked-in артефакты без явного `--write`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `make codex-onboard` | Read-only first screen для новой Codex-сессии | shell-only | нет | stdout |
| `make agent-verify` | Базовая проверка docs, OpenSpec, skills и context contract | shell + repo tooling | нет | stdout/stderr процесса |
| `make template-check-update` | Проверить, доступен ли новый wrapper overlay release | shell + git access к template source | нет | stdout/stderr процесса |
| `make export-context-preview` | Посмотреть generated-derived inventory без записи | shell-only | нет | preview в stdout |
| `make export-context-check` | Проверить свежесть generated-derived/context files | shell-only | нет | exit code |

Минимальный no-1C baseline:

```bash
make codex-onboard
make agent-verify
make export-context-check
```

Optional project-specific baseline extension:

- если `automation/context/runtime-support-matrix.json` объявляет `projectSpecificBaselineExtension`, относитесь к нему как к соседнему project-owned contour, а не к template baseline;
- advertising такого contour-а должно идти через runtime support matrix, `docs/agent/runtime-quickstart.md` и `make codex-onboard`;
- отсутствие extension по умолчанию не делает generated repo “неполным”.

## Profile-Required

Эти команды требуют валидный runtime profile и обычно пишут run artifacts в указанный `--run-root`.

| Command | Purpose | Prerequisites | Side effects | Artifacts |
| --- | --- | --- | --- | --- |
| `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | Проверка readiness runtime profile | 1С binaries и profile | пишет только run-root | `summary.json`, `stdout.log`, `stderr.log` |
| `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | Короткий runtime smoke contour | подготовленный profile | пишет только run-root | run-root logs и summary |
| `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | xUnit contour | подготовленный profile | пишет только run-root | run-root logs и summary |
| `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | BDD contour | подготовленный profile | пишет только run-root | run-root logs и summary |

Важно:

- shared runtime truth ищите сначала в `automation/context/runtime-support-matrix.md` / `.json`, а не в ignored local-private profiles;
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
