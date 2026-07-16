# Change: hardened warm runtime contours

## Why

Прикладной Delans-репозиторий подтвердил несколько reusable улучшений для шаблонных runtime-контуров:

- `xpra` может оставлять пользовательские `dbus/gvfs` процессы и со временем забивать лимиты файловых наблюдателей;
- warmed BDD-прогон должен уметь ловить ошибки из журнала регистрации, даже если Vanessa вернула успешный статус;
- golden baseline полезнее как готовый PostgreSQL snapshot restore/create контур, а не только как пустой project hook.

## What Changes

- Усилить `direct-platform` `xpra` wrapper очисткой дочерних и осиротевших `dbus/gvfs` процессов по session token/baseline.
- Расширить warmed BDD runner проверкой журнала регистрации, артефактами `eventlog*.json`, marker-сценарием завершения и подстановкой корня fixtures.
- Добавить reusable PostgreSQL golden snapshot scripts для `create` и `restore`, сохранив fail-closed поведение до явного profile/snapshot.
- Обновить fixture smoke, Makefile и generated-project guidance.

## Non-Goals

- Не переносить Delans BDD-сценарии, fixtures, расширения, имена ИБ или release items.
- Не добавлять Netlenka/GitLab release publisher в этот change; для него нужен отдельный параметризованный интерфейс.

## Impact

- Affected specs: `template-ci-contours`, `runtime-profile-schema`
- Affected code: `scripts/adapters/direct-platform.sh`, `scripts/test/run-bdd-warm-run.sh`, `scripts/test/run-bdd-warm-service.sh`, `scripts/test/run-golden-baseline.sh`, `tests/golden/*`, `tests/smoke/*`, `Makefile`, generated-project docs/templates
