# Env Examples

В этом каталоге лежат канонические runtime profile examples для launcher-скриптов.

## Важно

Launcher-скрипты могут загрузить runtime profile напрямую:

- через `--profile env/<name>.json`;
- через переменную `ONEC_PROFILE`;
- по умолчанию из `env/local.json`, если такой файл существует.

Versioned файлы `*.example.json` являются source of truth для формата профиля.
Рабочие профили `env/local.json`, `env/ci.json`, `env/wsl.json`, `env/windows-executor.json` не коммитятся.

`env/local.example.json` намеренно показывает mixed-profile contour:

- `create-ib`, `dump-src`, `update-db` остаются на `designer`;
- `load-src` переключен на `driver=ibcmd`;
- `ibcmd.runtimeMode=file-infobase`, чтобы partial import был wired через checked-in preset.

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

Дополнительные поля для `ibcmd` driver:

- `platform.ibcmdPath`
- `ibcmd.runtimeMode`
- `ibcmd.serverAccess.mode`
- `ibcmd.serverAccess.dataDir`
- mode-specific block:
  - `ibcmd.standalone.databasePath` для `runtimeMode=standalone-server`
  - `ibcmd.fileInfobase.databasePath` для `runtimeMode=file-infobase`
  - `ibcmd.dbmsInfobase.kind`
  - `ibcmd.dbmsInfobase.server`
  - `ibcmd.dbmsInfobase.name`
  - `ibcmd.dbmsInfobase.user`
  - `ibcmd.dbmsInfobase.passwordEnv`
- `ibcmd.auth.user` и `ibcmd.auth.passwordEnv` для `dump-src`, `load-src`, `update-db`

Дополнительные поля для WSL/Linux GUI isolation contour:

- `platform.xvfb.enabled`
- `platform.xvfb.serverArgs`

Этот contour является opt-in:

- включается только при `runnerAdapter=direct-platform`;
- требует локальные `xvfb-run` и `xauth`;
- применяется к standard-builder launches и к `command`-массивам, если basename исполняемого файла это `1cv8` или `1cv8c`;
- не меняет default behavior, если блок `platform.xvfb` отсутствует или выключен.

## Secrets

Секреты не хранятся в versioned JSON.

Вместо literal values profile хранит ссылки на переменные окружения:

- `infobase.auth.passwordEnv`
- `ibcmd.auth.passwordEnv`
- `ibcmd.dbmsInfobase.passwordEnv`

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

Если direct-platform contour запускается через `Xvfb`, capability `summary.json` и `doctor` summary добавляют structured `adapter_context` с выбранным wrapper и redacted `serverArgs`.

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

Если `platform.xvfb.enabled=true`, direct-platform adapter автоматически оборачивает только те `command`-массивы, где первый элемент указывает на локальный `1cv8` или `1cv8c`. Для `bash -lc ...` и других non-1C executables wrapper не включается.

## Ibcmd Runtime Modes

В текущем release поддерживаются три topology mode:

- `standalone-server`
- `file-infobase`
- `dbms-infobase`

Canonical examples:

- `env/wsl.example.json` показывает `standalone-server`
- `env/local.example.json` показывает `file-infobase`
- `env/ci.example.json` показывает `dbms-infobase`

Поддерживаемая support matrix:

- `runnerAdapter=direct-platform`
- `ibcmd.serverAccess.mode=data-dir`
- core capabilities `create-ib`, `dump-src`, `load-src`, `update-db`

Неподдерживаемые комбинации launcher отклоняет fail-closed и не делает silent fallback на `designer`.

Для XML source tree canonical format считается hierarchical.

Partial import поддерживается для `load-src` с `driver=ibcmd` и передаётся runtime input-ом. В текущем release этот contour поддержан для `standalone-server`, `file-infobase` и `dbms-infobase`:

```bash
./scripts/platform/load-src.sh --profile env/local.json --files "Catalogs/Items.xml,Forms/List.xml"
```

Если брать за основу `env/local.example.json`, дополнительная правка `loadSrc.driver` не нужна.

## Safety Warning For DBMS-Backed Contour

`dbms-infobase` является safety-sensitive contour.

- Он подходит для operator-owned standalone/dbms topology.
- Если целевая БД обычно принадлежит cluster-managed topology, template не считает такой contour автоматически безопасным.
- Ответственность за operational isolation и корректную подготовку БД лежит на операторе проекта.

## WSL / Linux Xvfb Contour

`env/wsl.example.json` является canonical preset для isolated GUI launches:

- `runnerAdapter=direct-platform`
- `platform.xvfb.enabled=true`
- `platform.xvfb.serverArgs=["-screen","0","1440x900x24","-noreset"]`
- core capabilities остаются на `designer`

Типовой запуск:

```bash
cp env/wsl.example.json env/wsl.json
./scripts/diag/doctor.sh --profile env/wsl.json
./scripts/platform/dump-src.sh --profile env/wsl.json --run-root /tmp/wsl-dump
```
