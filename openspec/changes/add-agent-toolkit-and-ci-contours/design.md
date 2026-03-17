## Context

Текущий шаблон уже содержит:

- `runner-agnostic` shell entrypoint’ы;
- update-ready delivery через `copier update`;
- managed overlays для `AGENTS.md`;
- базовые `scripts/platform/*` и `scripts/test/*`.

Но этого недостаточно для полноценного agentic workflow вокруг 1С. Сейчас в боевых репозиториях часть runtime-логики живет в project-local debug scripts и ad-hoc operational knowledge, а reusable skill packs из внешних репозиториев ориентированы в основном на Windows/PowerShell и не совпадают с Linux/WSL-first моделью этого шаблона.

## Goals / Non-Goals

- Goals:
  - сделать template source of truth для 1С agent runtime operations;
  - дать generated projects project-scoped skills, которые можно обновлять вместе с шаблоном;
  - разделить CI на безопасные контуры с явной границей между fixture и real-runtime jobs;
  - сохранить `copier update`-совместимость и не допустить дублирования логики между scripts и skills.
- Non-Goals:
  - не переносить целиком сторонние skill packs в шаблон;
  - не требовать Windows-only tooling как обязательный runtime;
  - не строить на первом этапе full MCP-first execution layer вместо versioned scripts;
  - не делать destructive runtime jobs обязательными для каждого PR.

## V1 Scope Boundary

В рамках этого change v1 считается следующим:

- reusable runtime substrate в template repo;
- тонкий слой project-scoped Claude skills;
- CI contours для шаблона и generated projects;
- Linux/WSL-first contract для локального и self-hosted runtime.

Вне v1:

- `remote-linux` как отдельный adapter с собственной транспортной моделью;
- обязательная metadata HTTP verification capability для каждого generated project;
- MCP execution plane как единственный способ работы с 1С;
- сложные browser/video workflows из внешних skill packs.

## Decisions

- Decision: использовать `script-first, skills-thin` архитектуру.
  - Why: versioned scripts удобнее тестировать, обновлять через template update и использовать из разных агентных контуров.
  - Consequence: `SKILL.md` описывает intent, входы и expected flow, но исполняемая логика живет в repo scripts.

- Decision: считать Linux/WSL-first runtime каноническим для generated projects, а adapter layer оставить pluggable.
  - Why: это соответствует текущему направлению шаблона и не делает `vrunner` фундаментальной зависимостью.
  - Consequence: direct platform и remote execution описываются как адаптеры под единым публичным contract.

- Decision: capability-скрипты обязаны возвращать machine-readable artifacts.
  - Why: агентам и CI нужны стабильные признаки успеха/ошибки, а не только текст stdout.
  - Consequence: каждая capability должна иметь `summary.json`, run-root и сырые логи.

- Decision: CI must be contour-based.
  - Why: template smoke и fixture tests можно запускать в обычном CI, а реальный 1С runtime требует self-hosted инфраструктуру и отдельные секреты.
  - Consequence: generated-project CI будет разделен на `static`, `fixture`, `runtime`.

- Decision: включить project-scoped `.claude/settings.json` в v1.
  - Why: skills должны поставляться как project-owned capability и не требовать ручной донастройки для каждого generated project.
  - Consequence: файл должен быть минимальным, без секретов и machine-specific paths.

- Decision: metadata HTTP verification contour оставить optional advanced capability.
  - Why: это полезный runtime pattern, но он зависит от project-specific HTTP services и не нужен каждому generated project на старте.
  - Consequence: v1 должен оставить extension point для этого contour, но не делать его hard requirement.

- Decision: `remote-linux` не делать обязательной частью v1.
  - Why: v1 должен сначала стабилизировать публичный capability contract на существующих adapter patterns, не расширяя matrix доставки раньше времени.
  - Consequence: design оставляет место для follow-up change с новым adapter без перелома public entrypoints.

## Target Repository Layout

Целевая раскладка generated project после внедрения v1:

```text
.
├── .claude/
│   ├── settings.json
│   └── skills/
├── .codex/
├── .github/
│   └── workflows/
├── env/
├── scripts/
│   ├── adapters/
│   ├── diag/
│   ├── lib/
│   ├── platform/
│   ├── qa/
│   └── test/
├── tests/
│   ├── smoke/
│   └── shell-fixtures/
└── openspec/
```

Назначение слоёв:

- `scripts/platform/` — публичные capability entrypoints для 1С runtime operations;
- `scripts/test/` — публичные entrypoints тестовых контуров;
- `scripts/diag/` — диагностика, классификация ошибок, preflight/doctor;
- `scripts/lib/` — переиспользуемый substrate: profile loading, platform resolution, common summary writers;
- `.claude/skills/` — thin agent wrappers над repo-owned scripts;
- `.github/workflows/` — layered CI contours;
- `tests/shell-fixtures/` — deterministic fixture coverage для shell/runtime логики без реальной платформы.

## Capability Contract

Каждый публичный capability entrypoint должен соблюдать единый contract:

- запускаться из versioned пути под `scripts/`;
- принимать явные входы через CLI flags и/или `--profile`;
- поддерживать `--run-root` для управления артефактами прогона;
- завершаться ненулевым exit code при ошибке;
- писать `summary.json` и сырые диагностические логи;
- не читать секреты из versioned файлов репозитория;
- для destructive/full-replace операций требовать явного подтверждения или opt-in flag.

Capability set v1:

- `scripts/platform/create-ib.sh`
- `scripts/platform/dump-src.sh`
- `scripts/platform/load-src.sh`
- `scripts/platform/update-db.sh`
- `scripts/platform/diff-src.sh`
- `scripts/test/run-xunit.sh`
- `scripts/test/run-bdd.sh`
- `scripts/test/run-smoke.sh`
- `scripts/diag/doctor.sh`

Optional advanced capability:

- `scripts/platform/publish-http.sh`
- `scripts/diag/smoke-http.sh`

## Runtime Profile Model

Generated projects должны иметь один канонический repo-owned формат runtime profiles.

Требования к profile model:

- source of truth хранится в versioned example-файлах в `env/`;
- реальные секреты и machine-specific overrides находятся вне Git или в local-only overrides;
- profile должен описывать:
  - adapter selection;
  - platform binary resolution;
  - IB connection parameters;
  - test contour configuration;
  - optional HTTP publish/smoke settings.

Шаблон не должен делать `.v8-project.json` источником истины для Linux/WSL-first runtime, но может позднее экспортировать compatibility metadata как follow-up enhancement.

## Skill Packaging Model

Каждый project-scoped skill должен:

- жить в versioned каталоге `.claude/skills/<skill-name>/`;
- ссылаться на repo-owned script entrypoint;
- описывать intent, expected inputs, safety notes и post-run checks;
- не копировать внутрь `SKILL.md` полную operational shell logic.

Минимальный набор skills v1:

- `1c-create-ib`
- `1c-dump-src`
- `1c-load-src`
- `1c-update-db`
- `1c-diff-src`
- `1c-run-xunit`
- `1c-run-bdd`
- `1c-run-smoke`
- `1c-doctor`

## CI Contours

Template-level CI:

- `template-static`
  - shell syntax
  - markdown / docs consistency checks
  - OpenSpec validation
- `template-fixture`
  - copier smoke
  - shell fixture tests
  - update regressions

Generated-project CI:

- `project-static`
  - traceability, docs and script lint checks
- `project-fixture`
  - shell/runtime fixture tests без реальной 1С
- `project-runtime`
  - реальные 1С jobs на self-hosted runner с labels и внешними secret sources

Правила для `project-runtime`:

- только self-hosted/provisioned runners;
- manual/protected triggers для destructive paths;
- отсутствие секретов и live connection details в template repo;
- документация по prerequisites обязательна.

## Alternatives Considered

- Перенести внешний skill pack как есть.
  - Rejected: он дублирует runtime contract, тащит Windows/PowerShell assumptions и плохо сочетается с template updates.

- Сразу строить execution через MCP-only layer.
  - Rejected: это увеличивает сложность первого шага и делает template зависимым от внешнего runtime без достаточной fixture-test базы.

- Оставить scripts и skills project-specific, без template source of truth.
  - Rejected: generated projects продолжат расходиться и терять benefit от `copier update`.

## Risks / Trade-offs

- Рост объема шаблона и числа поддерживаемых entrypoint’ов.
  - Mitigation: capability-driven decomposition и thin skills без дублирования логики.

- Конфликт между generic template contract и проектно-специфичными runtime overlays.
  - Mitigation: generic substrate в шаблоне, project-specific policies в generated repo overlay/config.

- Ошибки при runtime jobs в shared среде.
  - Mitigation: self-hosted only для `runtime` contour, manual/protected jobs для destructive операций.

## Migration Plan

1. Добавить OpenSpec requirements и согласовать contract.
2. Внедрить reusable substrate в `scripts/lib/`, `scripts/platform/`, `scripts/test/`, `scripts/diag/`.
3. Добавить shell fixture coverage и template smoke для нового substrate.
4. Добавить project-scoped skills и минимальный `.claude/settings.json`.
5. Добавить layered CI workflows для template и generated projects.
6. Обновить docs и выпустить tagged template version для rollout через `copier update`.
