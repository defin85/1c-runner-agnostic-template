# Change: добавить agent toolkit, project-scoped skills и CI contours для 1С-шаблона

## Why

Шаблон уже задает структуру репозитория и стабильные shell entrypoint’ы, но пока не содержит полного канонического набора runtime-скриптов и agent-facing skills для типовых 1С-операций. Из-за этого каждый generated project вынужден изобретать собственные скрипты, правила запуска и CI flow, а template update не может последовательно доставлять улучшения агентного tooling.

## What Changes

- Добавить script-first contract для взаимодействия агента с 1С-runtime: создание ИБ, загрузка/выгрузка конфигурации, diff, update DB, запуск тестов, публикация HTTP и диагностика.
- Добавить project-scoped skills, которые будут thin-wrapper’ами над versioned repo scripts, а не самостоятельным источником runtime-логики.
- Добавить CI contours для шаблона и generated projects с разделением на static, fixture и runtime/self-hosted слои.
- Зафиксировать Linux/WSL-first runtime model и adapter strategy для 1С-операций, не делая `vrunner` обязательной зависимостью.
- Зафиксировать machine-readable artifact contract (`summary.json`, run-root, logs) для capability-скриптов.

## V1 Scope

В первую версию входят только capability и артефакты, которые нужны для ежедневного agent-assisted development и которые можно стабильно доставлять через template update:

- repo-owned runtime substrate в `scripts/` и `env/`;
- project-scoped Claude skills как thin-wrapper над repo scripts;
- template CI для smoke/fixture/static проверок;
- generated-project CI skeleton с разделением на `static`, `fixture`, `runtime`;
- документация и operational contract для безопасного rollout.

Канонический capability set v1:

- `create-ib`
- `dump-src`
- `load-src`
- `update-db`
- `diff-src`
- `run-xunit`
- `run-bdd`
- `run-smoke`
- `doctor`

Advanced capability, которые можно включить в v1 только как optional contour, но не как hard requirement:

- `publish-http`
- `smoke-http`
- metadata verification contour

## Out Of Scope

- Полный перенос внешних skill packs в шаблон как есть.
- MCP-only execution layer вместо repo-owned scripts.
- Хранение реальных credentials, connection strings и machine-specific paths в шаблоне.
- Обязательный runtime contour для каждого PR в общей CI среде.
- Windows-only implementation как единственный поддерживаемый путь.

## Delivery Strategy

Изменение будет внедряться фазами:

1. Утвердить runtime contract, структуру каталогов и CI contours в OpenSpec.
2. Реализовать runtime substrate и fixture tests.
3. Поверх substrate добавить project-scoped skills.
4. Подключить CI workflows и обновить документацию.
5. Выпустить tagged версию шаблона для rollout через `copier update`.

## Impact

- Affected specs:
  - `agent-runtime-toolkit`
  - `project-scoped-skills`
  - `template-ci-contours`
- Affected code:
  - `scripts/platform/*`
  - `scripts/test/*`
  - `scripts/diag/*`
  - `.claude/skills/*`
  - `.claude/settings.json`
  - `env/*.example.json`
  - `.github/workflows/*`
  - `README.md`
  - `PROJECT_RULES.md`
