# Площадка заказчика

Эксплуатация серверов 1С и PostgreSQL заказчика, к которым оператор подключается
через VDI-клиент в фоновом Xpra либо через RDP. Документы и код появились в
проекте командой `make optional-module-init MODULE=customer-site-operations` и
дальше принадлежат проекту: шаблон их не обновляет.

| Документ | Когда читать |
|---|---|
| [rules.md](rules.md) | перед любой работой на площадке: ввод команд, sudo, rac, секреты |
| [inventory.md](inventory.md) | состав серверов, версии, службы, пути и базы; заполняет проект |
| [rac.md](rac.md) | `site-rac`: базы, сеансы, запрет входа, регламентные задания, лицензии |
| [ibcmd.md](ibcmd.md) | `site-ibcmd` и `site-dt-restore`: config-info, DT, копия базы из DT и её удаление |
| [golden.md](golden.md) | `site-golden-app` и `site-golden-db`: сохранение и восстановление набора эталонных баз |
| [archiving.md](archiving.md) | `site-db-archive`: архивирование и удаление прочих баз PostgreSQL |
| [techlog.md](techlog.md) | `site-techlog-control`: технологический журнал лицензий и ожиданий блокировок |
| [licensing.md](licensing.md) | `site-license-request`: офлайн-запрос программной лицензии |
| [v8users-recovery.md](v8users-recovery.md) | `site-v8users-recovery`: недокументированное восстановление доступа, отдельная опция |

Навыки: `site-vdi-xpra` (VDI-клиент в Xpra, ввод команд, keepalive) и
`site-rdp-bash-payload` (составные root-команды для ручного RDP-shell).

## Код и профили

- `infra/site/server/` — обёртки для серверов площадки. Только стандартная
  библиотека Python, запуск системным Python 3.7 и новее. Все обёртки читают
  общий профиль `site.json`, лежащий рядом с ними (`--profile` меняет путь).
- `infra/site/site.example.json` — пример профиля площадки с вымышленными
  значениями. Скопируйте его в `infra/site/site.json` и заполните; реальные
  `*.json` Git не отслеживает (`infra/site/.gitignore`).
- `infra/site/operator.example.json` — пример профиля хоста оператора для
  `./scripts/site/site-operator.sh`; рабочая копия — `infra/site/operator.json`.

Профиль площадки — список разрешённых баз. Изменяющие команды отказывают
(`REFUSED:`) до обращения к кластеру или СУБД, если база не указана в
`infobases`. Копия базы из DT и её удаление дополнительно требуют
`"disposable": true`.

## Установка обёрток на сервер

1. Каталог установки, например `/opt/site-ops/`, принадлежит `root`, права 0755.
   Пароли лежат отдельными файлами `root:root 0600` вне каталога установки;
   профиль ссылается на них путями.
2. Каждый файл `infra/site/server/*` переносите на сервер командами
   `./scripts/site/site-operator.sh transfer <файл> /opt/site-ops/<имя> 0755 --owner root:root`
   (для `site-common` — права 0644). Команды набирайте по одной; установка
   выполняется только после строки `sha256_match=1`.
3. Перенесите заполненный `site.json` тем же способом с правами 0600.
4. Проверьте установку read-only командой, например
   `python3 /opt/site-ops/site-rac list`.

Копия на сервере может отличаться от репозитория. Переустановка — отдельная
согласованная операция с машинной сверкой SHA-256.

## Проверка

```bash
make verify-python-tests ARGS="tests/python/test_customer_site_server.py tests/python/test_customer_site_operator.py"
```

Тесты шаблона проверяют заготовку модуля (`automation/optional/customer-site-operations/`)
и инструменты оператора на имитации `rac`, `psql`, `xdotool`; к площадке они не
обращаются. Если проект меняет свои копии обёрток в `infra/site/server/`, он
добавляет собственные тесты. Проверка на Python 3.7 запускается, если задана
переменная `SITE_SERVER_PYTHON` или в `PATH` есть `python3.7`.
