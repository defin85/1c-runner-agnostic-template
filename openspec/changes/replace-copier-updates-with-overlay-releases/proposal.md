# Change: replace copier updates with versioned overlay releases

## Why

Текущая модель ongoing updates опирается на `copier update` внутри generated repo. Для больших 1С-репозиториев это плохо масштабируется: даже если шаблон владеет только wrapper-layer, `copier update` всё равно вынужден reconcile-ить эволюцию всего subproject, включая большой `src/` tree.

Целевая модель проекта уже ближе к другому контракту: bootstrap делается один раз, а дальше target-репозиторий должен менять в основном только исходники конфигурации. Template-managed wrapper-layer должен поставляться как versioned overlay без попытки smart-merge поверх product source tree.

## What Changes

- Перевести generated-project maintenance path с `copier update` на `overlay release` модель.
- Оставить `copier copy` только для bootstrap нового проекта.
- Ввести checked-in manifest template-managed paths и version file overlay-состояния generated repo.
- Заменить `template-check-update` / `template-update` на overlay-aware check/apply flow, который работает только с managed paths.
- Сохранить post-apply refresh для generated README router, `AGENTS.md` overlay и generated-derived context.
- Перевести docs, smoke и QA checks на новую модель и убрать обещание ongoing `copier update` из primary maintenance docs.

## Impact

- Affected specs: `template-overlay-delivery`
- Affected code:
  - `scripts/template/*`
  - `scripts/bootstrap/*`
  - `tooling/update-1c-project`
  - `Makefile`
  - `docs/template-maintenance.md`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/source-vs-generated.md`
  - `README.md`
  - `tests/smoke/copier-update-ready.sh`
  - `tests/smoke/update-1c-project-wrapper.sh`
