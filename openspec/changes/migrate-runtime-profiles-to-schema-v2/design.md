## Context

Сейчас runtime profile contract в шаблоне опирается на `shellEnv` и строковые `*_CMD` значения. Для простых smoke cases это достаточно, но для реального хранения и использования параметров подключения к ИБ такой подход неудачен:

- topology и authentication смешиваются с shell quoting;
- profile нельзя валидировать как данные, только как текст;
- doctor может проверить лишь наличие `*_CMD`, но не корректность connection model;
- секреты легко утекают в versioned JSON или лог-сообщения, если operator копирует полный command string;
- migration для existing projects осложняется тем, что реальные `env/local.json` и `env/ci.json` находятся вне Git и не обновляются через template update.

## Goals / Non-Goals

- Goals:
  - сделать runtime profile источником структурированных данных, а не текстовых shell-команд;
  - явно разделить platform executables, infobase coordinates, auth и capability-specific options;
  - сделать `schemaVersion: 2` единственным поддерживаемым runtime contract;
  - зафиксировать безопасную работу с секретами через env-var indirection;
  - дать существующим generated projects понятный migration path.
- Non-Goals:
  - не поддерживать dual-mode `v1 + v2`;
  - не пытаться автоматически переписать ignored local profiles внутри `copier update`;
  - не строить полноценную integration с Vault/KMS как часть v2;
  - не заменять adapter architecture новым execution backend.

## Decisions

- Decision: `schemaVersion: 2` становится единственным поддерживаемым runtime profile format.
  - Why: dual-support удвоит сложность loader/doctor/docs, а текущий `v1` слишком stringly-typed, чтобы сохранять его как долгоживущий contract.
  - Consequence: все launcher scripts и doctor должны fail-closed на `schemaVersion: 1` с actionable migration error.

- Decision: параметры подключения к ИБ хранятся как структурированные данные, а не как готовые shell command strings.
  - Why: это упрощает валидацию, redaction, adapter-independent builders и безопасную документацию.
  - Consequence: loader должен читать explicit поля вроде `infobase.mode`, `infobase.server`, `infobase.ref`, `infobase.filePath`, а launcher scripts должны собирать argv сами.

- Decision: секреты хранятся только через environment variable indirection.
  - Why: versioned examples не должны содержать реальные значения, а CI/local runtime должен получать секреты из внешнего окружения.
  - Consequence: profile хранит имена переменных вроде `passwordEnv`, `dbPasswordEnv`, `clusterAdminPasswordEnv`, но не их значения.

- Decision: `IBConnectionString` может существовать только как explicit escape hatch override, а не как canonical source of truth.
  - Why: 1С поддерживает полный connection string, но он хуже валидируется и хуже подходит как базовая модель хранения.
  - Consequence: primary contract строится из structured fields; override допускается только для edge cases и должен быть mutually exclusive с canonical coordinates.

- Decision: migration для ignored local profiles должна быть manual-or-assisted, но не silent.
  - Why: `copier update` не переписывает ignored `env/local.json` и `env/ci.json`.
  - Consequence: change обязан поставить migration guide, helper/skeleton flow и понятную ошибку рантайма при обнаружении legacy profile.

- Decision: launcher-authored artifacts должны быть redacted.
  - Why: `summary.json` и diagnostic output являются машинно-читаемыми артефактами и не должны случайно дублировать секреты.
  - Consequence: summary отражает только safe metadata (`mode`, `server`, `ref`, `auth.mode`, `profile_path`, `adapter`) и никогда не пишет resolved passwords или fully assembled secret-bearing command lines.

## Proposed Schema Shape

Минимальная форма `schemaVersion: 2`:

```json
{
  "schemaVersion": 2,
  "profileName": "local",
  "runnerAdapter": "direct-platform",
  "platform": {
    "designerPath": "/opt/1cv8/x86_64/8.3.27.1859/1cv8"
  },
  "infobase": {
    "mode": "client-server",
    "server": "127.0.0.1:1541",
    "ref": "project_ref",
    "filePath": null,
    "connectionStringOverride": null,
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "dbms": {
    "authMode": "os",
    "user": null,
    "passwordEnv": null
  },
  "clusterAdmin": {
    "user": null,
    "passwordEnv": null
  },
  "capabilities": {
    "publishHttp": {
      "enabled": false
    }
  }
}
```

Правила модели:

- `infobase.mode` определяет mutually exclusive topology:
  - `file`
  - `client-server`
- для `file` требуется `filePath`;
- для `client-server` требуются `server` и `ref`;
- `connectionStringOverride` допустим только как explicit edge-case override;
- `auth.passwordEnv` и аналогичные поля содержат имя env var, а не secret value;
- capability-specific tuning хранится отдельным структурированным блоком, а не полным command blob.

## Migration Plan

1. Добавить `schemaVersion: 2` examples и migration guide в versioned файлы шаблона.
2. Добавить helper, который читает legacy profile и печатает skeleton для v2, насколько это возможно без угаданных секретов.
3. Обновить loader и doctor:
   - `schemaVersion: 2` -> normal path;
   - `schemaVersion: 1` -> fail with targeted migration message.
4. Обновить launcher scripts и CI/runtime docs на structured fields и env secret references.
5. Выпустить breaking tag и явно указать migration steps для generated projects.

## Risks / Trade-offs

- Existing generated projects не смогут просто запустить старый `env/local.json` после update.
  - Mitigation: migration guide, helper, explicit error message, breaking release communication.

- Some edge-case 1C setups используют сложные connection strings, которые не раскладываются чисто по canonical fields.
  - Mitigation: controlled `connectionStringOverride` как escape hatch, но не как default path.

- Даже при env-var indirection underlying 1C tooling теоретически может отразить отдельные connection details в stderr/stdout.
  - Mitigation: launcher scripts не логируют fully assembled secret-bearing argv и redaction policy распространяется на launcher-authored artifacts.

## Open Questions

- Нужно ли в v2 сразу вводить отдельный `enterprisePath`/`racPath`/`webinstPath`, или на первом шаге достаточно `designerPath` и adapter-specific defaults?
- Должен ли helper выполнять best-effort automatic conversion для simple `v1` profiles, или ограничиться генерацией skeleton + TODO markers?
