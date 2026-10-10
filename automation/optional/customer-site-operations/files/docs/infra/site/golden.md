# Эталонные базы (golden): сохранение и восстановление набора

Набор баз из `golden.bases` профиля сохраняется и восстанавливается целиком.
Работа разделена на два сервера; SSH между ними не нужен, файлы ticket и
receipt оператор переносит сам.

| Сервер | Обёртка | Назначение |
|---|---|---|
| Сервер приложений | `site-golden-app` | проверить регистрации, запретить вход и задания, выдать ticket; после receipt снять запрет входа |
| Сервер СУБД | `site-golden-db` | проверить PostgreSQL, сохранить или восстановить все БД набора местными утилитами, выдать receipt |
| Оба | `site-common` | общий код: профиль, проверки, журнал, атомарная запись файлов |

Восстановление пересоздаёт физические БД и сохраняет регистрации и UUID 1С.
Роли СУБД, настройки сервера, лицензии и внешние файлы в копию не входят.
Регламентные задания эталонных баз остаются запрещены и после снятия запрета
входа.

## Подготовка

- `golden.app_storage` (сервер приложений) и `golden.db_storage` (сервер СУБД) —
  отдельные постоянные каталоги владельца операции с правами 0700, не внутри
  каталога данных PostgreSQL и не в `/tmp`.
- Пароли — файлы `root:root 0600`: администратор кластера
  (`cluster.password_file`), администраторы баз (`infobases.*.password_file`),
  пользователь СУБД (`db_password_file`).
- Проверка: `site-golden-app check` и `site-golden-db check`. Они ничего не меняют.

## Сохранение набора

1. Сервер приложений:

   ```bash
   python3 /opt/site-ops/site-golden-app prepare --for capture --confirm 'BLOCK app_main+app_reference'
   ```

   Обёртка запрещает вход и задания всех баз набора, закрывает служебные
   соединения (сеансы пользователей она не завершает — закройте их заранее) и
   пишет `ticket-<operation>.json`.
2. Перенесите ticket на сервер СУБД (`site-operator transfer`, SHA-256).
3. Сервер СУБД:

   ```bash
   python3 /opt/site-ops/site-golden-db capture --ticket TICKET --operation OP \
     --confirm 'CAPTURE app_main+app_reference' --confirm-blocked OP
   ```

   `--confirm-blocked` повторяет идентификатор операции после того, как вы
   убедились, что запреты на сервере приложений активны. Итог — новое поколение
   (generation) с manifest и receipt.
4. Перенесите receipt на сервер приложений и снимите запрет входа:

   ```bash
   python3 /opt/site-ops/site-golden-app release --receipt RECEIPT --operation OP --confirm 'RELEASE OP'
   ```

## Проверка и восстановление

- `site-golden-db verify --generation G` сверяет файлы поколения с manifest.
- Восстановление: `site-golden-app prepare --for restore --generation G`, затем
  `site-golden-db restore --generation G --ticket ... --operation OP --confirm 'RESTORE G' --confirm-blocked OP`,
  затем `release`. Перед заменой обёртка сохраняет текущие БД в страховочное
  поколение (`safety_generation` в receipt).

## Ошибки и повтор

- Прерванная операция оставляет `pending.json` в хранилище. Повтор — та же
  команда с исходным ticket и `--resume`; новый `prepare` при незавершённой
  операции отказывает.
- При сбое `prepare` или `release` обёртка повторно включает запрет входа;
  базы остаются закрытыми до разбора.
- Если набор уже полностью восстановлен, повтор публикует receipt и не
  выполняет `DROP` повторно.
