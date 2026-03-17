# Env Examples

В этом каталоге лежат канонические runtime profile examples для launcher-скриптов.

## Важно

Launcher-скрипты могут загрузить runtime profile напрямую:

- через `--profile env/<name>.json`;
- через переменную `ONEC_PROFILE`;
- по умолчанию из `env/local.json`, если такой файл существует.

Versioned файлы `*.example.json` являются source of truth для формата профиля.
Рабочие профили `env/local.json`, `env/ci.json`, `env/windows-executor.json` не коммитятся.

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

Минимальные обязательные поля для standard direct-platform / remote-windows path:

- `platform.binaryPath`
- `infobase.mode`
- `infobase.filePath` для `mode=file`
- `infobase.server` и `infobase.ref` для `mode=client-server`

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
   Для `create-ib`, `dump-src`, `load-src`, `update-db` launcher строит argv сам из `platform` и `infobase`.

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

`diffSrc.command` тоже можно задать явно, но по умолчанию script использует `git diff -- ./src`.
