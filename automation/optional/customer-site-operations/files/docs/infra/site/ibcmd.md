# `site-ibcmd` и `site-dt-restore`: DT и копии баз

Обе обёртки запускаются на сервере приложений. Версия `ibcmd` должна совпадать
с `platform.version` профиля, база — быть в разделе `infobases`.

## `site-ibcmd`

| Команда | Что делает |
|---|---|
| `config-info --base B --output DIR` | выгружает `ConfigDumpInfo.xml` базы в новый каталог `DIR` |
| `dump --base B --output DIR [--dt-dir DT]` | выгружает DT; `--dt-dir` — новый каталог прямо внутри `dt.mount` |

- `dump` требует включённых запретов входа и регламентных заданий и отсутствия
  сеансов и соединений (служебное соединение RAS не считается).
- Перед выгрузкой обёртка проверяет привязку базы: СУБД PostgreSQL, имя БД
  совпадает с именем базы, сервер и пользователь СУБД — из профиля.
- Во время выгрузки обёртка останавливает `ibcmd`, если на диске назначения
  остаётся меньше 20 ГиБ или в рабочем каталоге меньше 5 ГиБ.
- Итог — `result.json` с размером и SHA-256 файла DT. Рядом с DT положите
  `SHA256SUMS` (`sha256sum <имя>.dt > SHA256SUMS`) и сохраните
  `config-info/ConfigDumpInfo.xml` этого запуска: он нужен для проверки копии.

`dt.mount` — каталог на сервере приложений, смонтированный с диска сервера СУБД
(`dt.source`, `dt.fstype` профиля). Обёртка сверяет источник монтирования через
`findmnt` и отказывает, если каталог смонтирован не оттуда.

## `site-dt-restore`

Без `--execute` выполняет только проверки и печатает `PREFLIGHT_PASS`.

### Восстановление DT в существующую базу

```bash
python3 /opt/site-ops/site-dt-restore --base app_main --dt /mnt/site-dt/RUN/app_main.dt --output /var/tmp/RUN-restore
python3 /opt/site-ops/site-dt-restore --base app_main --dt /mnt/site-dt/RUN/app_main.dt --output /var/tmp/RUN-restore --execute
```

- Регламентные задания базы должны быть запрещены, сеансов быть не должно.
- Обёртка на время загрузки включает запрет входа, проверяет SHA-256 DT по
  `SHA256SUMS`, сохраняет config-info до загрузки и после неё, затем
  возвращает прежний запрет входа. При сбое база остаётся закрытой.
- `--expect-config-info FILE` дополнительно сравнивает побайтно новый
  `ConfigDumpInfo.xml` с записанным при выгрузке DT.

### Согласованная копия базы из DT

Копия создаётся как новая БД и новая регистрация с запрещёнными регламентными
заданиями. Порядок:

1. Добавьте имя копии в `infobases` профиля с `"disposable": true` и
   `"auth_base": "<исходная база>"`: у копии те же пользователи, что в DT.
2. На сервере СУБД убедитесь, что БД с таким именем нет.
3. Запустите проверку, затем создание:

   ```bash
   python3 /opt/site-ops/site-dt-restore --base app_main_copy --create --confirm-db-absent app_main_copy \
     --dt /mnt/site-dt/RUN/app_main.dt --expect-config-info /mnt/site-dt/RUN/ConfigDumpInfo.xml \
     --output /var/tmp/RUN-copy --execute
   ```

4. Итог `CREATED` и `config_info_matches_dump: true` в `result.json` означают,
   что копия создана из проверенного DT и её конфигурация побайтно совпадает с
   конфигурацией на момент выгрузки.

### Удаление неудачной копии

Удаляется только база с `"disposable": true`, и никогда — эталонная (golden):

1. Сервер приложений: `python3 /opt/site-ops/site-rac jobs-off app_main_copy`, затем
   `python3 /opt/site-ops/site-rac unregister app_main_copy --confirm 'UNREGISTER app_main_copy'`.
2. Сервер СУБД:
   `python3 /opt/site-ops/site-golden-db discard-copy --database app_main_copy --confirm 'DROP app_main_copy'`.
3. Уберите копию из `infobases` профиля.

## Источники учётных данных

Пароль базы — файл `password_file` её записи в профиле (или записи из
`auth_base`), пароль СУБД — `db_password_file`. Оба файла `root:root 0600`.
Обёртки передают пароли только в аргументы `ibcmd` и `rac`, не выводят argv и
сырой вывод; журнал ошибки маскирует пароли.
