## Context

В template уже есть driver-model для `ibcmd`, но она спроектирована как phase-1 contour вокруг одного локального сценария.
На практике этого недостаточно:

- `ibcmd` требует разный набор параметров для standalone data directory, file infobase и DBMS-backed infobase;
- часть параметров относится не к auth самой ИБ, а к DBMS topology;
- команды `create`, `config import`, `config export`, `config apply` имеют mode-specific argv contract;
- у пользователя есть валидный operational запрос на PostgreSQL-backed contour, который типично воспринимается как "кластерная ИБ".

При этом template не должен:

- плодить второй публичный namespace скриптов;
- silently fallback между `designer` и `ibcmd`;
- маскировать риск работы standalone tools против cluster-managed topology.

## Goals / Non-Goals

- Goals:
  - сохранить стабильные `scripts/platform/create-ib.sh`, `dump-src.sh`, `load-src.sh`, `update-db.sh`;
  - расширить `ibcmd` profile contract так, чтобы он выражал три режима:
    - `standalone-server`
    - `file-infobase`
    - `dbms-infobase`
  - сделать mode-specific credentials и DBMS coordinates явными и machine-validated;
  - зафиксировать mode-specific argv requirements для `create-ib`, `dump-src`, `load-src`, `update-db`;
  - оставить secret indirection через env vars;
  - фиксировать выбранный `ibcmd` mode в machine-readable artifacts.
- Non-Goals:
  - не переводить `ibcmd` в отдельный `runnerAdapter`;
  - не вводить новый публичный набор launcher-скриптов;
  - не обещать поддержку всех `ibcmd` access paths (`--pid`, `--remote`) в этом change;
  - не добавлять auto-discovery DBMS parameters через `rac` или cluster admin tooling;
  - не объявлять безопасной работу standalone utilities против активной cluster-managed IB без явной operator-owned подготовки.

## Decisions

- Decision: различать topology mode и capability driver.
  - `driver=ibcmd` отвечает за toolchain.
  - `ibcmd.runtimeMode` отвечает за topology/credential shape.
  - Consequence: один и тот же driver может иметь разные обязательные поля в profile.

- Decision: в этом change фиксируются три runtime modes:
  - `standalone-server`
  - `file-infobase`
  - `dbms-infobase`
  - Consequence: текущий phase-1 `data-dir` контур становится частным случаем, а не единственным поддержанным сценарием.

- Decision: transport/access path остаётся узким и явным.
  - Для этого change template моделирует локальный direct execution contour через `runnerAdapter=direct-platform`.
  - `--pid` и `--remote` считаются follow-up scope.
  - Consequence: change расширяет topology coverage без одновременного взрыва support matrix по transport modes.

- Decision: `dbms-infobase` — это DBMS-backed contour, совместимый с cluster-derived topology, но не implicit promise безопасной работы against active cluster-managed database.
  - Consequence: docs и validation должны отдельно предупреждать, что operator отвечает за корректную operational isolation.

- Decision: profile schema для `ibcmd` становится mode-specific.
  - `standalone-server` использует structured standalone block.
  - `file-infobase` использует явный путь к file DB.
  - `dbms-infobase` использует `dbms.kind`, `server`, `name`, `user`, `passwordEnv`.
  - Consequence: toolkit обязан валидировать только релевантные mode-specific fields.

- Decision: capability builders обязаны следовать реальному CLI contract `ibcmd`, а не designer-shaped mental model.
  - Consequence:
    - `create-ib` не должен слепо подставлять infobase auth там, где она не применима;
    - `config import`/`config export` должны использовать mode-appropriate positional and named args;
    - `config apply` должен явно выражать non-interactive policy.

## Proposed Runtime Model

### 1. Driver Selection

Публичные entrypoints остаются прежними.
Core capability по-прежнему выбирает `driver` per capability:

- `createIb.driver`
- `dumpSrc.driver`
- `loadSrc.driver`
- `updateDb.driver`

Если выбран `driver=ibcmd`, runtime дополнительно читает:

```json
{
  "ibcmd": {
    "runtimeMode": "standalone-server | file-infobase | dbms-infobase"
  }
}
```

### 2. Structured Ibcmd Shape

Базовый shape:

```json
{
  "platform": {
    "ibcmdPath": "/opt/1cv8/x86_64/8.3.27.1859/ibcmd"
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "/var/lib/onec/standalone"
    },
    "auth": {
      "user": "standalone-admin",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  }
}
```

Mode-specific blocks:

```json
{
  "ibcmd": {
    "runtimeMode": "standalone-server",
    "standalone": {
      "databasePath": "/var/lib/onec/standalone/db"
    }
  }
}
```

```json
{
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "fileInfobase": {
      "databasePath": "/var/lib/onec/file-ib"
    }
  }
}
```

```json
{
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "192.168.32.143 port=5432;",
      "name": "develop",
      "user": "postgres",
      "passwordEnv": "ONEC_DBMS_PASSWORD"
    }
  }
}
```

Принципы:

- `ibcmd.auth` — это credentials уровня infobase/runtime tool, если они требуются operation contract;
- `ibcmd.dbmsInfobase.*` — это отдельный secret-bearing contour для DBMS;
- `infobase.auth.*` остаётся source of truth для user-facing infobase auth на designer path и для capability-level visibility;
- DBMS password всегда хранится как env-var reference.

### 3. Support Matrix

Этот change вводит три topology modes, но не обещает все transport modes.

Supported in scope:

- `runnerAdapter=direct-platform`
- `driver=ibcmd`
- `ibcmd.serverAccess.mode=data-dir`
- `ibcmd.runtimeMode`:
  - `standalone-server`
  - `file-infobase`
  - `dbms-infobase`

Out of scope for this change:

- `ibcmd.serverAccess.mode=pid`
- `ibcmd.serverAccess.mode=remote`
- auto-discovery of DBMS/cluster parameters via `rac`

### 4. Capability Semantics

- `create-ib`
  - MUST use mode-specific create contract
  - MUST NOT inject irrelevant auth flags
- `dump-src`
  - MUST follow `ibcmd config export` contract for the selected mode
  - MUST preserve hierarchical XML as canonical source tree
- `load-src`
  - MUST follow `ibcmd config import` contract for full and partial modes
  - partial import remains explicit runtime input, not static-only profile state
- `update-db`
  - MUST use non-interactive update policy and documented acceptance semantics

## Alternatives Considered

- Keep `data-dir` as the only supported contour and treat DBMS-backed topology as custom `command`.
  - Rejected: это превращает ключевой user-facing contour в undocumented escape hatch.

- Add a second `ibcmd` public script namespace.
  - Rejected: ломает stable capability facade.

- Model cluster-backed topology as mandatory `clusterAdmin` + auto-import from cluster metadata.
  - Rejected for this change: в repo нет стабильной `rac` abstraction, а scope становится больше, чем нужно для корректной runtime schema.

- Expand both topology modes and access modes in one step.
  - Rejected: слишком широкая support matrix и высокий риск half-working implementation.

## Risks / Trade-offs

- Schema becomes more complex.
  - Mitigation: mode-specific blocks и fail-closed validation.

- Users may read `dbms-infobase` as blanket approval to work against a live cluster-managed database.
  - Mitigation: docs и doctor должны явно маркировать этот contour как operator-owned and safety-sensitive.

- `ibcmd` CLI differs from designer mental model.
  - Mitigation: capability-level requirements must describe CLI semantics explicitly.

- Partial import and update semantics can diverge by topology.
  - Mitigation: mode-specific tests and machine-readable driver context.

## Migration Plan

1. Existing profiles without `driver=ibcmd` remain unchanged.
2. Existing `ibcmd` profiles migrate by:
   - replacing implicit phase-1 assumptions with `ibcmd.runtimeMode`;
   - moving topology-specific coordinates into mode-specific blocks.
3. Docs and examples must show one canonical example for each supported mode.

## Open Questions

- Нужно ли в этом же change добавлять explicit cluster-admin metadata import helper, или direct DBMS coordinates достаточно для first supported `dbms-infobase` contour?
  - Proposed answer: direct DBMS coordinates достаточно; cluster-admin import вынести в follow-up.
