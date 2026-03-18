## Context

Сейчас template уже умеет:

- держать стабильные capability entrypoint-скрипты;
- выбирать `runnerAdapter` для transport/execution path;
- строить standard builder для `create-ib`, `dump-src`, `load-src` и `update-db` вокруг `1cv8 DESIGNER` и `CREATEINFOBASE`.

Проблема в том, что `ibcmd` не укладывается в текущую модель как "еще один adapter". Он меняет не только способ исполнения команды, но и сам toolchain:

- использует отдельный бинарник;
- работает со standalone server, а не с generic `DESIGNER /F|/S` contract;
- имеет свои ограничения по authentication, connection model и XML format contract;
- поддерживает не только full operations, но и partial import/export для configuration XML.

Если добавить второй публичный набор скриптов, template потеряет ключевое свойство stable capability facade. Если добавить `ibcmd` в `runnerAdapter`, transport layer смешается с tool semantics.

## Goals / Non-Goals

- Goals:
  - сохранить один публичный набор core runtime entrypoints;
  - отделить transport adapter от capability driver;
  - дать минимальный phase-1 путь для подключения `ibcmd` без ломки default designer flow;
  - покрыть `create-ib`, `dump-src`, `load-src`, `update-db` и partial import path для `load-src`;
  - сделать profile contract и validation явными и fail-closed.
- Non-Goals:
  - не переводить весь runtime toolkit на новую driver-модель за один change;
  - не делать `ibcmd` обязательным или default path;
  - не вводить параллельный namespace скриптов;
  - не расширять phase 1 на capabilities, где equivalence между `designer` и `ibcmd` пока не зафиксирована;
  - не объявлять все `runnerAdapter` и все `ibcmd` connection modes поддержанными с первого шага.

## Decisions

- Decision: оставить публичные `create-ib`, `dump-src`, `load-src` и `update-db` как единственную внешнюю поверхность.
  - Why: это сохраняет стабильный contract для людей, CI и агентов.
  - Consequence: выбор backend должен происходить внутри toolkit, а не через другой путь к скрипту.

- Decision: разделить `runnerAdapter` и `driver`.
  - Why: `runnerAdapter` отвечает за transport/execution path, а `driver` отвечает за то, каким 1С-инструментом реализуется конкретный capability.
  - Consequence: `ibcmd` не добавляется как новый `runnerAdapter`; вместо этого `dumpSrc` и `loadSrc` получают собственный `driver`.

- Decision: ограничить phase 1 только core runtime capabilities `create-ib`, `dump-src`, `load-src`, `update-db`.
  - Why: пользовательский runtime flow вокруг `ibcmd` должен быть целостным: создание ИБ, выгрузка/загрузка конфигурации и применение database configuration не должны распадаться на разные механизмы без явной причины.
  - Consequence: `publish-http`, test contours и прочие non-core capabilities остаются за пределами этого change.

- Decision: для `ibcmd` использовать отдельный structured profile block.
  - Why: существующих `platform.binaryPath` и `infobase` полей недостаточно, чтобы выразить standalone-server connection model и ограничения `ibcmd`.
  - Consequence: profile должен явно описывать путь к `ibcmd`, mode подключения и standalone auth-поля, а toolkit должен валидировать их до запуска.

- Decision: default path остается `designer`.
  - Why: generated projects уже завязаны на текущий contract, и phase 1 должен быть non-breaking для существующих profile examples.
  - Consequence: отсутствие `driver` в поддерживаемых capabilities трактуется как `designer`.

- Decision: phase 1 intentionally narrows the `ibcmd` support matrix.
  - Why: у `ibcmd` разные execution semantics для `--data`, `--pid` и `--remote`, а часть команд недоступна в некоторых remote scenarios.
  - Consequence: change обязан явно фиксировать, какие adapter/mode combinations поддерживаются, а остальные сочетания отвергать fail-closed.

- Decision: canonical XML source tree для `ibcmd` path фиксируется как hierarchical-only.
  - Why: `ibcmd` поддерживает import/export XML только в hierarchical format, тогда как designer path потенциально допускает более широкую матрицу форматов.
  - Consequence: docs и profile examples не должны оставлять эту часть неявной.

- Decision: partial import of selected XML files становится частью phase 1 только для `load-src`.
  - Why: diff-aware loading это отдельный user-facing runtime need, который нельзя надежно выразить static profile-only настройкой.
  - Consequence: у `load-src` должен появиться explicit contract для selected-file import, а docs должны фиксировать driver support matrix для partial mode.

- Decision: неподдерживаемые комбинации profile и driver должны отклоняться fail-closed.
  - Why: silent fallback между `designer` и `ibcmd` замаскирует реальные topology/auth problems и усложнит диагностику.
  - Consequence: doctor и launcher scripts обязаны валидировать support matrix до runtime invocation.

- Decision: raw `command` override и canonical driver selection не должны смешиваться в рамках одной capability.
  - Why: иначе generated project может незаметно обойти validation, summary semantics и capability-specific guarantees.
  - Consequence: profile contract должен явно задать precedence или mutual exclusion rule.

## Proposed Model

### 1. Two-Axis Runtime Resolution

Toolkit выбирает реализацию capability в два шага:

1. transport adapter
   Определяет, как подготовленная команда будет исполнена: локально, через `remote-windows` wrapper и т.д.
2. capability driver
   Определяет, какой toolchain строит argv/command для конкретного capability.

Для phase 1:

- `create-ib.driver`: `designer | ibcmd`
- `dump-src.driver`: `designer | ibcmd`
- `load-src.driver`: `designer | ibcmd`
- `update-db.driver`: `designer | ibcmd`

Если driver отсутствует:

- toolkit MUST использовать `designer`.

### 2. Runtime Profile Shape

Минимальное расширение profile:

```json
{
  "platform": {
    "binaryPath": "/opt/1cv8/x86_64/8.3.27.1859/1cv8",
    "ibcmdPath": "/opt/1cv8/x86_64/8.3.27.1859/ibcmd"
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "/var/lib/onec/standalone",
    "remote": null,
    "pid": null,
    "auth": {
      "user": "admin",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "createIb": {
      "driver": "designer"
    },
    "dumpSrc": {
      "driver": "designer",
      "outputDir": "./src/cf"
    },
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf",
      "partialMode": "full"
    },
    "updateDb": {
      "driver": "designer"
    }
  }
}
```

Принципы модели:

- existing `platform.binaryPath` и `infobase` contract сохраняются для `designer`;
- `platform.ibcmdPath` обязателен только при выборе `ibcmd`;
- `ibcmd` connection block активируется только для capabilities, где выбран `ibcmd`;
- phase 1 MUST явно фиксировать разрешенные значения `ibcmd.connectionMode`;
- partial import не должен кодироваться только в static profile: runtime contract должен предусматривать передачу selected file set в момент запуска;
- template docs должны явно описывать standalone-only характер `ibcmd` path и hierarchical-only contract для XML source tree.

### 3. Support Matrix

Phase 1 matrix:

- supported transport adapter:
  - `direct-platform`
- unsupported until follow-up change:
  - `remote-windows`
  - `vrunner`
- supported `ibcmd.connectionMode`:
  - один явно зафиксированный safe mode из phase 1 contract
- unsupported until follow-up change:
  - все остальные `ibcmd.connectionMode`
- `dump-src`:
  - `designer`: supported
  - `ibcmd`: supported
- `load-src`:
  - `designer`: supported
  - `ibcmd`: supported
- `create-ib`:
  - `designer`: supported
  - `ibcmd`: supported
- `update-db`:
  - `designer`: supported
  - `ibcmd`: supported
- `load-src` partial import:
  - `ibcmd`: supported
  - `designer`: implementation-defined in phase 1 and MUST be documented explicitly
- `diff-src`, test contours, `publish-http`:
  - вне scope этого change

Неподдерживаемые или неописанные комбинации не должны silently fallback на другой driver.

### 4. Partial Import Contract

`load-src` должен поддерживать два runtime режима:

1. full import
   Загружается вся конфигурация из source tree.
2. partial import
   Загружается только явно выбранный набор XML-файлов конфигурации.

Для phase 1:

- partial import должен принимать selected file set как явный runtime input;
- пути к XML-файлам должны быть относительными к configured source directory;
- docs должны явно описывать, поддерживается ли partial import для каждого driver.

## Alternatives Considered

- Добавить второй публичный набор скриптов `scripts/ibcmd/*`.
  - Rejected: дублируется capability contract, документация, tests и agent bindings.

- Добавить `ibcmd` как новый `runnerAdapter`.
  - Rejected: это смешивает transport concerns с tool semantics и ухудшает profile validation.

- Делать driver selection глобальным для всего profile.
  - Rejected: разные capabilities имеют разную степень эквивалентности между `designer` и `ibcmd`; phase 1 должен оставаться узким.

- Оставить partial/diff loading только через raw `command` arrays.
  - Rejected: это не дает стабильного capability contract и ломает traceability/validation для важного user-facing runtime flow.

## Risks / Trade-offs

- Profile schema становится сложнее.
  - Mitigation: ограничить driver-модель core runtime capabilities и оставить `designer` default.

- Пользователь может ожидать, что после появления `ibcmd` весь runtime toolkit автоматически станет driver-agnostic.
  - Mitigation: явно задокументировать phase-1 boundary и support matrix.

- Поведение `load-src` и `update-db` может отличаться между toolchains на уровне внутренних шагов.
  - Mitigation: нормализовать contract на уровне capability intent, partial/full mode и отражать выбранный driver в machine-readable artifacts.

- Возможны скрытые ограничения `ibcmd` по auth/topology, которые не выражаются текущими полями `infobase`.
  - Mitigation: использовать отдельный `ibcmd` block и fail-closed validation вместо implicit reuse.

- Partial import может оказаться неодинаково выразимым для разных drivers.
  - Mitigation: сделать driver support matrix явной частью контракта и не обещать parity там, где она не реализована.

## Open Questions

- Какой именно `ibcmd.connectionMode` фиксируется в phase 1 как единственный supported path: `data-dir` или другой локальный режим?
- Должен ли partial import в phase 1 быть доступен только для `ibcmd`, или его нужно сразу нормализовать и для `designer` driver?
