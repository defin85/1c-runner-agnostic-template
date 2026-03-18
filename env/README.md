# Env Examples

В этом каталоге лежат канонические runtime profile examples для launcher-скриптов.

## Важно

Launcher-скрипты могут загрузить runtime profile напрямую:

- через `--profile env/<name>.json`;
- через переменную `ONEC_PROFILE`;
- по умолчанию из `env/local.json`, если такой файл существует.

Versioned файлы `*.example.json` являются source of truth для формата профиля.
Рабочие профили `env/local.json`, `env/ci.json`, `env/windows-executor.json` не коммитятся.

`env/local.example.json` намеренно показывает mixed-profile contour:

- `create-ib`, `dump-src`, `update-db` остаются на `designer`;
- `load-src` переключен на `driver=ibcmd`, чтобы partial import был wired через checked-in preset.

`schemaVersion: 1` больше не поддерживается. Existing local profiles нужно мигрировать вручную:

- helper: `./scripts/template/migrate-runtime-profile-v2.sh <legacy-profile>`
- guide: `docs/migrations/runtime-profile-v2.md`

## Canonical SchemaVersion 2 Shape

Каждый profile должен содержать:

- `schemaVersion`
- `profileName`
- `runnerAdapter`
- `platform`
- `infobase`
- `capabilities`

Минимальные обязательные поля для default `designer` path:

- `platform.binaryPath`
- `infobase.mode`
- `infobase.filePath` для `mode=file`
- `infobase.server` и `infobase.ref` для `mode=client-server`

Дополнительные поля для `ibcmd` driver в phase 1:

- `platform.ibcmdPath`
- `ibcmd.connectionMode`
- `ibcmd.dataDir`
- `ibcmd.auth.user`
- `ibcmd.auth.passwordEnv`
- `ibcmd.databasePath` только если `createIb.driver = "ibcmd"`

## Secrets

Секреты не хранятся в versioned JSON.

Вместо literal values profile хранит ссылки на переменные окружения:

- `infobase.auth.passwordEnv`
- `dbms.passwordEnv`
- `clusterAdmin.passwordEnv`

Пример:

```json
{
  "auth": {
    "mode": "user-password",
    "user": "ci-user",
    "passwordEnv": "ONEC_IB_PASSWORD"
  }
}
```

Перед запуском:

```bash
export ONEC_IB_PASSWORD='...'
./scripts/diag/doctor.sh --profile env/ci.json
```

## Capability Contract

Каждый capability entrypoint под `scripts/platform/`, `scripts/test/` и `scripts/diag/`:

- принимает `--profile`;
- поддерживает `--run-root`;
- пишет `summary.json`, `stdout.log`, `stderr.log`;
- возвращает ненулевой exit code на failure;
- не пишет resolved secrets в `summary.json`.

## Capabilities Block

В `schemaVersion: 2` есть два пути конфигурации capability:

1. standard builder
   Для `create-ib`, `dump-src`, `load-src`, `update-db` launcher строит argv сам и выбирает backend по `capabilities.<id>.driver`.
   Если `driver` опущен, используется `designer`.

2. profile-defined command array
   Для project-specific contour вроде `xunit`, `bdd`, `smoke`, `publishHttp` profile задаёт `command` как массив строк:

```json
{
  "capabilities": {
    "xunit": {
      "command": ["bash", "-lc", "echo TODO: run xUnit"]
    }
  }
}
```

`driver` и `command` взаимоисключающие для одной capability.

`diffSrc.command` тоже можно задать явно, но по умолчанию script использует `git diff -- ./src`.

## Ibcmd Phase 1

Поддерживаемая матрица phase 1:

- `runnerAdapter=direct-platform`
- `ibcmd.connectionMode=data-dir`
- core capabilities `create-ib`, `dump-src`, `load-src`, `update-db`

Неподдерживаемые комбинации launcher отклоняет fail-closed и не делает silent fallback на `designer`.

Для XML source tree canonical format считается hierarchical.

Partial import поддерживается только для `load-src` с `driver=ibcmd` и передаётся runtime input-ом:

```bash
./scripts/platform/load-src.sh --profile env/local.json --files "Catalogs/Items.xml,Forms/List.xml"
```

Если брать за основу `env/local.example.json`, дополнительная правка `loadSrc.driver` не нужна.
