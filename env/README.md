# Env Examples

В этом каталоге лежат канонические runtime profile examples для launcher-скриптов.

## Важно

Launcher-скрипты могут загрузить runtime profile напрямую:

- через `--profile env/<name>.json`;
- через переменную `ONEC_PROFILE`;
- по умолчанию из `env/local.json`, если такой файл существует.

Versioned файлы `*.example.json` являются source of truth для формата профиля.
Рабочие профили `env/local.json`, `env/ci.json`, `env/windows-executor.json` не коммитятся.

Каждый profile должен содержать:

- `schemaVersion`
- `profileName`
- `runnerAdapter`
- `shellEnv`

## Базовые переменные

- `RUNNER_ADAPTER`
- `CREATE_IB_CMD`
- `DUMP_SRC_CMD`
- `LOAD_SRC_CMD`
- `UPDATE_DB_CMD`
- `DIFF_SRC_CMD`
- `PUBLISH_HTTP_CMD`
- `XUNIT_RUN_CMD`
- `BDD_RUN_CMD`
- `SMOKE_RUN_CMD`
- `BSL_LANGUAGE_SERVER_JAR`

Для `remote-windows` и `vrunner` используются отдельные варианты переменных, см. примеры ниже.

## Capability Contract

Каждый capability entrypoint под `scripts/platform/`, `scripts/test/` и `scripts/diag/`:

- принимает `--profile`;
- поддерживает `--run-root`;
- пишет `summary.json`, `stdout.log`, `stderr.log`;
- возвращает ненулевой exit code на failure.
