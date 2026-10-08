---
name: 1c-observe-run
description: Используйте, когда длительный запуск 1С (Designer, клиент, загрузка, обновление) идёт долго, завис или упал и нужно понять его состояние по артефактам наблюдения, не вмешиваясь в процесс.
metadata:
  short-description: Диагностика длительного запуска 1С по observation.jsonl и техжурналу.
---

# Agent Skill: 1c-observe-run

Repo script: `./scripts/diag/technological-log.sh`
Windows launcher: `./scripts/diag/technological-log.ps1`

## Когда использовать

- Штатная capability (`create-ib`, `load-src`, `update-db`, `dump-src` и другие) или `run-client --wait` работает дольше ожидаемого.
- Запуск завершился с кодом `124`, `125` или `70`, и нужно понять причину.
- Нужно найти ошибки платформы, относящиеся только к этому запуску.

## Что пишет адаптер наблюдения

Каждый наблюдаемый запуск пишет в свой `--run-root`:

- `observation.jsonl` — события schema v1: одно `started`, `heartbeat` каждые `ONEC_OBSERVATION_INTERVAL_SECONDS` секунд (по умолчанию 30, допустимо 1..30), события `tech-event` и ровно одно завершающее событие `completed` или `failed` с полями `exitCode` и `terminalReason`.
- `summary.json` — раздел `observation`: `terminalEvent`, `terminalReason`, `exitCode`, `heartbeatCount`, `diagnosticCount`, `status` (`ok` или `degraded`).
- `stdout.log`, `stderr.log`, `process.pid` — PID процесса платформы.
- `progress.txt` — файл прогресса, путь к нему процесс получает в `ONEC_OBSERVATION_PROGRESS_FILE`.
- `technological-log-cursor.json` и `technological-log-restore.json` — если включён технологический журнал.

Значения `terminalReason`:

| Причина | Код | Что произошло |
|---|---|---|
| `completed` | 0 | Команда завершилась успешно, ожидаемый результат есть. |
| `command-exit` | код процесса | Команда завершилась с ненулевым кодом. |
| `missing-result` | 70 | Код 0, но ожидаемого файла результата нет. |
| `timeout` | 124 | Общий лимит истёк до первого сообщения о прогрессе. |
| `stalled` | 125 | Содержимое файла прогресса не менялось дольше порога; группа процессов остановлена. |
| `launch-failed` | 127 | Процесс не удалось запустить. |
| `operator-stop` | код процесса | Клиент остановлен командой `run-client stop`. |

Остановка при неизменном прогрессе происходит только при заданном пороге: `ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS` для capability или `--idle-timeout` для `run-client`. Без порога heartbeat только сообщает `stageAgeSeconds` — сколько секунд прогресс не менялся.

## Порядок диагностики

1. Прочитать последнюю строку `[observation] ... event=heartbeat` в stderr запуска: `elapsed`, `source` (`progress`, `output` или `quiet`), `stage` и `stage_age`.
2. Прочитать `observation.jsonl` в run-root: есть ли завершающее событие, какой `terminalReason`, есть ли `degraded` и `degradedReason`.
3. Прочитать раздел `observation` в `summary.json`.
4. Если включён технологический журнал, прочитать события только этого запуска:

   ```bash
   ./scripts/diag/technological-log.sh cursor read --state <run-root>/technological-log-cursor.json --all
   ```

5. Только после этого смотреть журнал регистрации информационной базы.

## Технологический журнал

- Журнал включается, только если оператор задал `TECHLOG_CONFIG_PATH` — путь к `logcfg.xml` платформы. Необязательные параметры: `TECHLOG_ROOT` (каталог журнала, по умолчанию `<run-root>/techlog`), `TECHLOG_SERVER_ROOT` (каталог журнала сервера для клиент-серверной базы), `TECHLOG_PRIVILEGED_COMMAND` (команда повышения прав для записи `logcfg.xml`, по умолчанию `none`).
- На время запуска адаптер записывает ограниченный `logcfg.xml`: события `EXCP`, `TDEADLOCK`, `TTIMEOUT` и `TLOCK` длительностью больше 100 мс, хранение 1 час. События `CALL`, `SCALL`, `SDBL`, SQL-события и `SYSTEM` не включаются.
- После запуска исходный `logcfg.xml` восстанавливается побайтно, в том числе после ошибки. Если исходного файла не было, временный файл удаляется. Результат записан в `technologicalLog.restored` завершающего события.
- Если наблюдающий процесс был убит и `logcfg.xml` остался временным, восстановите исходный файл:

  ```bash
  ./scripts/diag/technological-log.sh status
  ./scripts/diag/technological-log.sh restore --run-root <run-root>
  ```

  Следующий наблюдаемый запуск тоже восстанавливает оригинал, если владелец временного файла уже не работает.

## Запреты

- Не читать полную командную строку процесса платформы (`/proc/<pid>/cmdline`, `ps -f`, `ps aux`, `wmic`, `Get-CimInstance Win32_Process`): в ней может быть пароль базы. Для поиска процесса использовать `process.pid` из run-root.
- Не останавливать процесс вручную, пока heartbeat продолжается и причина не понятна. Для клиента использовать `run-client stop --run-root <run-root>`.
- Не включать в `logcfg.xml` события `CALL`, `SCALL`, `SDBL`, SQL и `SYSTEM` и не оставлять полный технологический журнал включённым после запуска.
- Не копировать в отчёт текст из `progress.txt` и описания ошибок с данными информационной базы; в heartbeat попадает только короткий статус из символов `A-Z a-z 0-9 _ . : -`.
