# Generated Operator-Local Runbook Starter Reference

Этот template-scoped reference описывает expected contract для project-owned `docs/agent/operator-local-runbook.md`.

## Runbook Contract

- отвечает на вопрос “реально ли этот contour runnable здесь и чего не хватает?”;
- остаётся project-owned bridge для `operator-local` и `provisioned` contour-ов;
- ссылается на `automation/context/runtime-support-matrix.md`, `.json`, `docs/agent/runtime-quickstart.md`, `env/README.md`, `docs/agent/generated-project-verification.md`;
- перечисляет canonical `operator-local` contour-ы `doctor`, `check-x11-contour`, `load-cfe`, `configure-cfe-runtime-flags`, `check-cfe-applicability`, `check-cfe-config`, `load-diff-src`, `load-task-src`, `yaxunit`, `yaxunit-warm-rpc`, `web-client-diagnostic`, обязательный `golden-baseline`, `bdd`, `bdd-warm-service`, `smoke` и `publish-http`;
- для multi-target extension workspace фиксирует `automation/context/target-matrix.json`, явный `--target <id>` и profile `.target.id` как проверяемую связку;
- перед запуском YAxUnit, YAxUnit warm-RPC или BDD warm-service фиксирует выборочную синхронизацию: сначала обновлять только нужное расширение через `--target <id> --extension <name>`, а полный `load-cfe --target <id>` использовать только для первичной подготовки ИБ или изменения `extensionMatrix`;
- для single-target workspace сохраняет canonical entrypoint-ы `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` и `./scripts/platform/load-task-src.sh --profile env/local.json --work-item 93984 --run-root /tmp/load-task-src-run`;
- фиксирует canonical entrypoint-ы `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run`, `./scripts/diag/check-x11-contour.sh --profile env/local.json`, `./scripts/platform/load-cfe.sh --profile env/local.json --target ut22 --extension ProjectTests --run-root /tmp/load-cfe-project-tests`, `./scripts/test/sync-yaxunit-runtime.sh --profile env/local.json --target ut22 --extension YAxUnitTests --run-root /tmp/yaxunit-sync-run`, `./scripts/platform/load-diff-src.sh --profile env/local.json --target ut22 --run-root /tmp/load-diff-src-run`, `./scripts/platform/load-task-src.sh --profile env/local.json --target ut22 --work-item 93984 --run-root /tmp/load-task-src-run`, `./scripts/test/run-yaxunit.sh --profile env/local.json`, `./scripts/test/run-yaxunit-warm-service.sh up --profile env/local.json`, `./scripts/test/run-web-client-diagnostic.sh --profile env/local.json`, `./tests/golden/create.sh --profile env/local.json --target ut22`, `./scripts/test/run-golden-baseline.sh --profile env/local.json --target ut22 --run-root /tmp/golden-baseline-run` и `./scripts/test/run-bdd-warm-service.sh up --profile env/local.json --run-root /tmp/bdd-warm-service-run`;
- для Vanessa BDD warm-service фиксирует `automation/context/operator-local-targets.json`, Vanessa Automation Single path, warmup feature и project-owned обработчик `capabilities.bddWarmService.launchParameterName` как prerequisite split;
- для Vanessa BDD warm-service фиксирует, что менеджер и клиент тестирования стартуют отдельными 1С-сеансами, готовность требует `READY` от менеджера и слушающий `TestClient` порт, параллельные запуски должны иметь разные `--run-root`, warmup feature подключается к уже поднятому клиенту по порту вместо запуска нового клиента через сохранённый профиль Vanessa Automation, а warmed BDD runner может fail-closed проверять журнал регистрации;
- для `direct-platform` `xpra` фиксирует ожидание очистки wrapper-owned `dbus/gvfs` процессов при остановке runtime contour-а;
- фиксирует preflight checks, canonical entrypoint-ы, env/profile provenance и expected fail-closed states;
- не делает ignored local-private profile shared baseline truth.
