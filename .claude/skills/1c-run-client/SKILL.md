---
name: 1c-run-client
description: Используйте, когда нужно открыть клиент 1С для базы из runtime profile, посмотреть экран, нажать клавишу или кнопку, дождаться завершения обработки или остановить клиент.
metadata:
  short-description: Интерактивный клиент 1С в собственном Xpra-сеансе run-root.
---

# Agent Skill: 1c-run-client

Repo script: `./scripts/platform/run-client.sh`
Windows launcher: `./scripts/platform/run-client.ps1`

## Когда использовать

- Нужно открыть базу из runtime profile в режиме предприятия и проверить форму или обработку.
- Нужно выполнить внешнюю обработку (`--execute`) и дождаться её завершения с проверкой результата.
- Нужно сделать снимок экрана клиента, отправить клавишу или щелчок, узнать состояние или закрыть клиент.

## Команды

```bash
# Открыть клиент в фоне; команда возвращается, когда клиент готов
./scripts/platform/run-client.sh start --profile env/local.json --run-root /tmp/client-run
./scripts/platform/run-client.sh start --profile env/local.json --url e1cib/list/Справочник.Номенклатура

# Выполнить обработку и дождаться закрытия клиента
./scripts/platform/run-client.sh start --profile env/local.json --run-root /tmp/epf-run \
  --execute build/check.epf --c /tmp/epf-run/progress.txt \
  --wait --timeout 600 --result-file /tmp/epf-run/result.json \
  --idle-timeout 120 --progress-file /tmp/epf-run/progress.txt

# Действия только над клиентом своего run-root
./scripts/platform/run-client.sh screenshot --run-root /tmp/client-run
./scripts/platform/run-client.sh key --run-root /tmp/client-run Escape
./scripts/platform/run-client.sh click --run-root /tmp/client-run 640 400
./scripts/platform/run-client.sh status --run-root /tmp/client-run
./scripts/platform/run-client.sh stop --run-root /tmp/client-run

# Проверить параметры запуска без запуска; пароль показан как ***
./scripts/platform/run-client.sh start --profile env/local.json --dry-run
```

## Поведение

- Подключение и пароль берутся только из runtime profile: пароль читается из переменной окружения, имя которой задано в `infobase.auth.passwordEnv`. В выводе, `summary.json`, `stdout.log` и `stderr.log` пароль заменяется на `***`.
- На Linux клиент запускается в собственном Xpra-сеансе своего `--run-root` (в профиле нужен `platform.xpra.enabled=true`). Дисплей сеанса записан в `<run-root>/xpra/active-display.env`, PID клиента — в `<run-root>/process.pid`.
- `screenshot`, `key`, `click`, `status` и `stop` действуют только на клиента своего run-root. Если `process.pid` указывает на процесс, который не является клиентом 1С этого run-root, команда завершается с ошибкой и ничего не делает. `screenshot`, `key` и `click` работают только на Linux.
- Запуск наблюдается общим адаптером: в run-root пишутся `observation.jsonl` и раздел `observation` в `summary.json`. Разбор — навык `1c-observe-run`.
- Результат `start --wait`:

  | `status` | Код | Условие |
  |---|---|---|
  | `finished` | 0 | Клиент закрылся; файл `--result-file`, если задан, существует. |
  | `no-result` | 70 | Клиент закрылся с кодом 0, но файла `--result-file` нет. |
  | `timeout` | 124 | `--timeout` истёк, а файл прогресса ещё ни разу не записан (без `--progress-file` это общий лимит); сохраняется `screenshots/timeout.png`, клиент закрывается. |
  | `idle-timeout` | 125 | После первой записи содержимое `--progress-file` не менялось `--idle-timeout` секунд; сохраняется `screenshots/idle-timeout.png`, клиент закрывается. |
  | `failed` | код клиента | Клиент завершился с ошибкой. |

- `--idle-timeout` и `--progress-file` задаются только вместе и только с `--wait`. Файл прогресса и файл результата не должны существовать до запуска. Путь к файлу прогресса обработка получает через `--c` или собственный параметр.
- При коде 125 сначала открыть `screenshots/idle-timeout.png`: обычно клиент ждёт ответа в модальном окне.

## Запреты

- Не запускать `1cv8`/`1cv8c` напрямую и не передавать пароль в аргументах команд (`/P`, `--password`, `--db-pwd` в `db-run` и других навыках). Использовать этот навык и `infobase.auth.passwordEnv`.
- Не вызывать `xpra`, `xdotool`, `import` или `xwininfo` для чужого дисплея и не подключаться к дисплею другого run-root или пользователя.
- Не читать командную строку процесса клиента (`/proc/<pid>/cmdline`, `ps -f`, `ps aux`): в ней есть пароль.
- Не использовать один `--run-root` для двух клиентов: `start` отказывается запускаться, если в run-root уже есть `run-client.json`.
