# Change: расширить runtime-модель ibcmd до трёх режимов

## Why

Текущий `ibcmd`-контракт в шаблоне слишком узкий и не соответствует реальной модели утилиты.
Сейчас runtime фактически предполагает один phase-1 путь вокруг `data-dir`, тогда как operational reality для `ibcmd` распадается минимум на три разных topologies:

- `standalone-server`
- `file-infobase`
- `dbms-infobase` для ИБ, которые живут в PostgreSQL/MS SQL/DB2/Oracle и типично ассоциируются с cluster contour

Из-за этого template не может корректно выразить mode-specific credentials, DBMS coordinates и различия между core operations `create-ib`, `dump-src`, `load-src`, `update-db`.

## What Changes

- расширить `ibcmd` profile contract с одного узкого `data-dir` contour до трёх явных runtime modes;
- ввести mode-specific structured fields для:
  - standalone server topology;
  - file infobase topology;
  - DBMS-backed topology;
- зафиксировать, что stable public entrypoints не меняются, а mode selection остаётся внутренним driver concern;
- зафиксировать fail-closed validation для несовместимых mode/field combinations;
- зафиксировать redacted machine-readable visibility выбранного `ibcmd` mode;
- подготовить implementation contract для корректной argv-сборки `ibcmd` по capability и mode.

## Impact

- Affected specs:
  - `ibcmd-capability-drivers`
  - `runtime-profile-schema`
- Affected code:
  - `scripts/lib/ibcmd.sh`
  - `scripts/lib/onec.sh`
  - `scripts/diag/doctor.sh`
  - `env/*.example.json`
  - `tests/smoke/runtime-ibcmd-*.sh`
