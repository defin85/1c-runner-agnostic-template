# Заготовка модуля `customer-site-operations`

Модуль добавляет в проект регламент и инструменты эксплуатации площадки заказчика: серверы 1С и
PostgreSQL, к которым оператор подключается через VDI-клиент в фоновом Xpra или через RDP. Включается
командой `make optional-module-init MODULE=customer-site-operations` (Windows:
`./make.ps1 optional-module-init customer-site-operations`).

Файлы из `files/` копируются в проект по тем же относительным путям и дальше принадлежат проекту:

- `infra/site/server/` — обёртки для серверов площадки на стандартной библиотеке Python 3.7+:
  `site-rac` (в том числе `jobs-on`/`jobs-off`), `site-ibcmd`, `site-dt-restore` (DT и согласованная
  копия базы), `site-golden-app`/`site-golden-db` (эталонные базы и удаление неудачной копии),
  `site-db-archive`, `site-techlog-control`, `site-license-request` и отдельная опция
  `site-v8users-recovery`;
- `infra/site/site.example.json`, `infra/site/operator.example.json` — примеры профилей с вымышленными
  значениями; рабочие `*.json` Git не отслеживает;
- `docs/infra/site/` — регламент площадки, шаблон инвентаризации и описание каждой обёртки;
- `.agents/skills/site-vdi-xpra/`, `.agents/skills/site-rdp-bash-payload/` — навыки (дополнительно
  копируются в `.claude/skills/`).

Инструменты хоста оператора `scripts/site/site-operator.sh` и `scripts/python/site_operator.py` остаются
template-managed и обновляются через `template-update`. Тесты `tests/python/test_customer_site_server.py`
и `tests/python/test_customer_site_operator.py` проверяют заготовку в шаблоне, а
`tests/smoke/customer-site-deidentified.sh` — что в заготовке нет данных конкретного заказчика.

Данные площадки (адреса, имена серверов и баз, учётные записи, результаты операций) в шаблон не входят:
проект вносит их в свои `site.json`, `operator.json` и `docs/infra/site/inventory.md`.
