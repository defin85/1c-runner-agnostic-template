# Env Examples

В этом каталоге лежат примеры конфигурации окружения.

## Важно

Текущие launcher-скрипты читают shell env vars напрямую.

JSON-файлы в этом каталоге нужны как:

- контракт конфигурации окружения;
- шаблон для CI/CD;
- источник значений для bootstrap-скрипта, который вы можете добавить позже.

## Базовые переменные

- `RUNNER_ADAPTER`
- `CREATE_IB_CMD`
- `LOAD_SRC_CMD`
- `UPDATE_DB_CMD`
- `PUBLISH_HTTP_CMD`
- `XUNIT_RUN_CMD`
- `BDD_RUN_CMD`
- `SMOKE_RUN_CMD`
- `BSL_LANGUAGE_SERVER_JAR`

Для `remote-windows` и `vrunner` используются отдельные варианты переменных, см. примеры ниже.
