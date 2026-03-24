## 1. Overlay Delivery Contract

- [x] 1.1 Ввести versioned overlay state и manifest template-managed paths для generated repos.
- [x] 1.2 Реализовать materialize/check/apply flow для overlay release без `copier update`.
- [x] 1.3 Сохранить bootstrap через `copier copy` и post-copy initialization без regressions.

## 2. Generated Repo Maintenance Path

- [x] 2.1 Перевести `make template-check-update` и `make template-update` на overlay-aware behavior.
- [x] 2.2 Обновить helper `tooling/update-1c-project` под новый contract.
- [x] 2.3 Сохранить post-apply refresh для managed README router, `AGENTS.md` overlay и generated-derived context.

## 3. Docs And Verification

- [x] 3.1 Переписать source/generated docs так, чтобы ongoing maintenance не рекламировал `copier update`.
- [x] 3.2 Обновить smoke tests и QA checks под overlay apply/check flow.
- [x] 3.3 Прогнать `openspec validate --strict --no-interactive`, `make agent-verify` и relevant smoke tests.
