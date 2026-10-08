# Импортированные навыки: вывод редакторов метаданных и запуск через runtime profile

Запись release notes для созданных проектов. Изменения приходят обычным `make template-update` (`./make.ps1 template-update`).

## Выведенные навыки

`template-update` удаляет из `.agents/skills` и `.claude/skills` импортированные навыки:

- `meta-info`, `meta-compile`, `meta-edit`, `meta-remove`, `meta-validate`;
- `form-info`, `form-add`, `form-compile`, `form-edit`, `form-remove`, `form-validate`;
- `cfe-borrow`.

Их заменяет CLI `metadata` и навык `metadata-use`. Навык `form-patterns` остаётся. Команда `sync-imported-skills` больше не копирует эти навыки из upstream `cc-1c-skills`, а `./scripts/skills/run-imported-skill.sh <имя>` отвечает `imported skill not found in manifest`.

Что сделать в проекте: заменить вызовы выведенных навыков в своих сценариях и регламентах на `metadata` (`metadata-use`). Проектные копии этих навыков под другими именами `template-update` не трогает.

## `db-*`, `epf-*` и `erf-*` работают только через runtime profile

Импортированные навыки больше не запускают Designer напрямую и не создают временную ИБ:

| Навык | Новое поведение |
| --- | --- |
| `db-load-cf`, `db-dump-cf`, `db-load-xml`, `db-dump-xml` | `ibcmd config load|save|import|export` по профилю; параметры `[-Profile <json>] [-RunRoot <dir>] -InputFile|-OutputFile|-ConfigDir <path> [-Extension <имя>]` |
| `epf-build`, `erf-build` | `ibcmd config import --out=<файл>` по профилю; `[-Profile <json>] [-RunRoot <dir>] -SourceFile <xml> -OutputFile <файл>` |
| `epf-dump`, `erf-dump` | `ibcmd config export --file=<файл>` по профилю; `[-Profile <json>] [-RunRoot <dir>] -InputFile <файл> -OutputDir <dir>` |
| `db-create`, `db-update`, `db-load-git` | прокси в `create-ib`, `update-db`, `load-diff-src`; запуск отклоняется, если у capability `createIb`, `updateDb` или `loadSrc` в профиле не задан `driver: ibcmd` |
| `db-run` | прокси в `run-client` (`1c-run-client`); форма с `-V8Path`, `-InfoBase*`, `-Password` отклоняется |

- Без `-Profile`/`--profile` используется `ONEC_PROFILE` или `env/local.json`. Если профиля нет, запуск завершается ошибкой до старта платформы.
- Параметры `-V8Path`, `-InfoBasePath`, `-InfoBaseServer`, `-InfoBaseRef`, `-UserName`, `-Password` больше не принимаются. Подключение и источники паролей берутся из профиля.
- Каждый запуск пишет в run-root `summary.json`, `stdout.log`, `stderr.log` и `observation.jsonl`. Пароли в них заменены на `__REDACTED_SECRET__`. Без `-RunRoot` каталог создаётся в `.artifacts/imported-skills/`.
- Остановка при неизменном прогрессе включается только порогом `ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS`, который задаёт вызывающая обёртка.
- `-DryRun` публикует `summary.json` с командой без запуска ibcmd.

Что сделать в проекте: завести runtime profile со схемой `schemaVersion: 3` и секцией `ibcmd`; для `db-create`, `db-update`, `db-load-git` выбрать `driver: ibcmd`; заменить в своих сценариях вызовы с `-V8Path`/`-InfoBase*` на `-Profile <json>`. Проекты без runtime profile теряют прямой запуск этих навыков через Designer.

Проверка после обновления:

```bash
./scripts/skills/run-imported-skill.sh epf-build --help
./scripts/skills/run-imported-skill.sh db-load-cf -Profile env/local.json -InputFile <cf> -DryRun
```
