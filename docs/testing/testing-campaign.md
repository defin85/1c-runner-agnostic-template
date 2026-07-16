# Кампания тестирования

Кампания хранит последовательную очередь длительного прогона в `analysis/testing/campaigns/<id>/`. Инструмент рассчитан на одного писателя: не запускайте две команды изменения состояния одновременно и не редактируйте `queue.jsonl` параллельно вручную.

## Подготовка инструментария

```bash
./scripts/test/init-test-tooling.sh --project-tests-name ProjectYAxUnitTests
./scripts/test/install-test-tooling.sh
```

Первая команда без сети создаёт четыре project-owned дерева: `src/cfe/VATestContour`, `src/cfe/ProjectYAxUnitTests`, `src/cfe/YAxUnit` и `src/cfe/VAExtension`. Она никогда не заменяет существующие каталоги. Вторая устанавливает Vanessa Automation Single в `.artifacts/testing/vanessa/1.2.043.28/vanessa-automation-single.epf`; для автономной установки передайте `--archive <zip>`.

После инициализации настройте `extensionMatrix`, выполните `check-cfe-config`, `check-cfe-applicability` и `load-cfe`. В профиле укажите:

```json
{"capabilities":{"bddWarmService":{"vanessaSinglePath":".artifacts/testing/vanessa/1.2.043.28/vanessa-automation-single.epf"}}}
```

## Формат

`entrypoints.json` содержит только отображаемые строки. Инструмент их не исполняет и не подставляет переменные. Не помещайте в них пароли и токены; используйте переменные окружения и локальные runtime-профили.

```json
{
  "prepareGolden": "./tests/golden/restore.sh --profile env/local.json --target ut",
  "startWarmService": "./scripts/test/run-bdd-warm-service.sh up --profile env/local.json",
  "runJob": "ONEC_PROFILE_PATH=env/local.json ONEC_TARGET_ID=ut ONEC_BDD_FEATURES=<featurePath> ./scripts/test/run-bdd-warm-run.sh"
}
```

Пример очереди `queue.jsonl`:

```jsonl
{"id":"bdd-login","kind":"vanessa-bdd","status":"pending","selector":{"featurePath":"features/login.feature"}}
{"id":"unit-common","kind":"yaxunit","status":"pending","selector":{"filters":{"extensions":["ProjectYAxUnitTests"],"tags":["smoke"]}}}
```

`vanessa-bdd` преобразуется в явный запуск одного feature-файла:

```bash
ONEC_PROFILE_PATH=env/local.json ONEC_TARGET_ID=ut ONEC_BDD_FEATURES="features/login.feature" ./scripts/test/run-bdd-warm-run.sh
```

`yaxunit` запускается после синхронизации расширений; значения `filters` передаются одноимённым параметрам существующего запуска:

```bash
./scripts/test/run-yaxunit.sh --profile env/local.json --target ut --extension ProjectYAxUnitTests --tag smoke
```

Разрешены фильтры `extensions`, `modules`, `tests`, `tags`, `paths`; каждый заданный фильтр — непустой массив строк. Инструмент кампании только возвращает selector как JSON и сам эти команды не запускает.

## Работа

```bash
./scripts/test/testing-campaign.sh init --id release-1 --queue queue.jsonl --entrypoints entrypoints.json
./scripts/test/testing-campaign.sh use release-1
./scripts/test/testing-campaign.sh next
./scripts/test/testing-campaign.sh set bdd-login running
./scripts/test/testing-campaign.sh set bdd-login done --result-dir .artifacts/test-runs/bdd-login
./scripts/test/testing-campaign.sh status
```

Приоритет `next`: `failed_retry`, затем `running`, затем `pending`; при исчерпании возвращается `job: null`. Переходы: `pending → running|blocked|skipped_by_policy`, `running → done|failed_retry|blocked`, `failed_retry → running|blocked|skipped_by_policy`. Состояния `done`, `blocked`, `skipped_by_policy` конечные. Для `done` обязателен `resultDir`, для остальных он запрещён.

Схема fail-closed: поддерживается только `schemaVersion: 1`; неизвестные поля, состояния, виды задания, повторяющиеся id, абсолютные пути, `..` и символические ссылки отклоняются. Записи выполняются атомарной заменой файла. Человек или агент продолжает работу одинаково: выбирает кампанию, получает `next`, запускает существующий тестовый entrypoint и фиксирует результат через `set`.

Откат исходников выполняется Git revert. Для отката Vanessa укажите в профиле путь к сохранённой предыдущей версии в `.artifacts/testing/vanessa/<version>/`.
