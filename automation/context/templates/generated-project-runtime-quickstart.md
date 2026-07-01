# Generated Runtime Quickstart Starter Reference

Этот template-scoped reference описывает expected contract для project-owned `docs/agent/runtime-quickstart.md`.

## Runtime Quickstart Contract

- даёт короткий ответ на вопрос “что здесь реально можно запустить и с какими prerequisites?”;
- использует те же contour ids и status vocabulary, что `automation/context/runtime-support-matrix.md` и `.json`;
- в multi-target extension workspace показывает `--target <id>` для source, CFE и target-bound test contours и ссылается на `automation/context/target-matrix.json`;
- перед тестовыми контурами показывает выборочную синхронизацию runtime (`sync-yaxunit-runtime.sh --target <id> --extension <name>` или `load-cfe.sh --target <id> --extension <name>`) вместо полной загрузки всех расширений;
- использует `docs/agent/operator-local-runbook.md` как bridge для `operator-local` contour-ов;
- описывает `bdd-warm-service` как operator-local Vanessa contour с двумя 1С-сеансами (`/TESTMANAGER` и `/TestClient`), local-private Vanessa inputs, project-owned обработчиком `launchParameterName`, готовностью по `READY` и открытому порту клиента тестирования;
- уточняет, что параллельные BDD warm-service запуски должны использовать разные `--run-root`, warmup feature подключается к уже поднятому клиенту по порту, а warmed BDD runner может проверять журнал регистрации через `capabilities.bdd.eventLogDir`;
- описывает `golden-baseline` как PostgreSQL snapshot restore contour с `golden-create` для создания `.artifacts/golden/target-id.dump`;
- отмечает, что `direct-platform` `xpra` wrapper очищает wrapper-owned `dbus/gvfs` хвосты после завершения;
- ссылается на `docs/agent/generated-project-verification.md`, `env/README.md` и checked-in runtime support matrix как на canonical truth;
- ссылается на `automation/context/recommended-skills.generated.md` и `make imported-skills-readiness` как на AI-ready companion layer для first-hour skill routing;
- отделяет template baseline от optional project-specific baseline extension;
- остаётся digest-слоем и не заставляет читать весь общий runtime contract для первого ответа.
